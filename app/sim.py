"""Multi-week simulator.

Compares three ways of keeping a "one introduction per person every week" promise on the same
synthetic pool, with the same random draws for who says yes and who drifts away:

  greedy      first come first served: each person takes their best free candidate
  one_shot    optimal pool-wide matching every week, but no memory of who missed out
  weekly_drop one_shot plus carry-over: priority and a gently relaxed floor for people who waited

People who wait several weeks without an introduction drift away. That is the cost of a broken promise.
"""
from __future__ import annotations

import copy
import hashlib
import math
import random
from dataclasses import dataclass, field, replace

import networkx as nx
import numpy as np

from . import compat, trust
from .cohort import make_cohort
from .drop import DropConfig, run_greedy, run_matching, supply_gaps
from .models import User

POLICIES = ["greedy", "one_shot", "weekly_drop"]
POLICY_LABEL = {"greedy": "First come, first served", "one_shot": "Best pairing, no memory",
                "weekly_drop": "Weekly Drop"}

YES_CENTER = 0.55     # a person says yes about half the time to a 0.55 directional score
YES_STEEPNESS = 12.0
CHURN_PER_WAIT = 0.06  # weekly chance of leaving, times weeks waited (capped at 4 weeks)
CHRONIC_GHOSTERS = 0.10   # share of people who often go quiet after a mutual yes
GHOST_PROB = {"chronic": 0.65, "ordinary": 0.12}
CLOSE_RATE = 0.40         # assumption: with the closure protocol, this share of would-be ghosts close kindly
ADMIT_SLACK = 1.15        # balanced admission: the larger side is admitted up to 1.15x the smaller side, per city


def rand01(seed: int, *parts) -> float:
    h = hashlib.sha256(("|".join(str(p) for p in (seed, *parts))).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def p_yes(directional_score: float) -> float:
    return 1.0 / (1.0 + math.exp(-YES_STEEPNESS * (directional_score - YES_CENTER)))


@dataclass
class SimParams:
    n: int = 200
    weeks: int = 6
    pct_women: float = 0.45
    pct_nonbinary: float = 0.02
    inflow_pct: float = 0.10       # new people joining each week, as a share of n
    seed: int = 11
    floor: float = 0.62
    coverage_bias: float = 0.35
    cities: list[tuple[str, float]] | None = None
    realistic: bool = False        # give people stated deal-breakers (strict intent, privacy circles, verified only)
    adv_pct: float = 0.0           # share of joiners who are scam accounts (red-team runs)
    trust_gate: bool = False       # hold back risky accounts before matching
    reports: bool = False          # real people can report a scammer after being introduced
    ghosting: bool = False         # model people going quiet after a mutual yes
    closure: bool = False          # closure protocol: kind close with a reason, small priority cost for ghosting
    admission: bool = False        # balanced admission: waitlist the oversupplied side, longest waiters first
    ceiling: bool = False          # also compute the best any policy could do (max-cardinality matching)


@dataclass
class WeekRow:
    week: int
    pool: int
    intros: int
    covered: float            # share of the pool that received an introduction
    avg_score: float
    strong_share: float       # share of intros in the Strong tier
    mutual_per_100: float     # mutual yes per 100 people in the pool
    waited_2plus: float       # share of the pool that has now waited 2 or more weeks
    left: int                 # people who drifted away this week
    intent_mismatch: float = 0.0   # share of introductions where the two people differ on intent
    waitlisted: int = 0       # admitted later on purpose (balanced admission)
    covered_all: float = 0.0  # introduced, as a share of everyone who is a member, waitlisted or not
    ceiling: float = 0.0      # the most coverage any policy could reach at the loosest floor
    unreachable: float = 0.0  # share of the pool with nobody they could ever be introduced to


@dataclass
class PolicyRun:
    policy: str
    rows: list[WeekRow] = field(default_factory=list)
    final_active: int = 0
    total_joined: int = 0
    retention: float = 0.0
    supply: list[dict] = field(default_factory=list)
    unmatched_reasons: dict[str, int] = field(default_factory=dict)
    all_scores: list[float] = field(default_factory=list)
    person: list[dict] = field(default_factory=list)
    trust: dict = field(default_factory=dict)
    ghost: dict = field(default_factory=dict)


def _cfg(p: SimParams) -> DropConfig:
    return DropConfig(floor=p.floor, coverage_bias=p.coverage_bias, ghost_penalty=0.05 if p.closure else 0.0)


def _prep(users: list[User], params: SimParams) -> None:
    if params.adv_pct > 0:
        trust.attach_signals(users, params.seed)
    if params.ghosting:
        for u in users:
            chronic = rand01(params.seed, "chronic", u.id) < CHRONIC_GHOSTERS
            u.ghost_prob = GHOST_PROB["chronic" if chronic else "ordinary"]


def base_cohort(params: SimParams) -> list[User]:
    users = make_cohort(params.n, seed=params.seed, pct_women=params.pct_women, pct_nonbinary=params.pct_nonbinary,
                        cities=params.cities, realistic=params.realistic)
    if params.adv_pct > 0:
        users += trust.make_adversaries(int(round(params.n * params.adv_pct)), params.seed, 0, "x")
    _prep(users, params)
    return users


def _ceiling(m: compat.Matrices, cfg: DropConfig) -> tuple[float, float]:
    cand = m.eligible & (m.mutual >= cfg.min_floor)
    n = len(m.users)
    if n == 0:
        return 0.0, 0.0
    G = nx.Graph()
    ii, jj = np.where(np.triu(cand, 1))
    G.add_edges_from(zip(ii.tolist(), jj.tolist()))
    pairs = nx.max_weight_matching(G, maxcardinality=True)
    return 2 * len(pairs) / n, float((cand.sum(axis=1) == 0).sum()) / n


def _admit(live: list[User], seed: int) -> tuple[list[User], list[User]]:
    """Balanced admission. Per city the larger of men and women is admitted up to ADMIT_SLACK x the smaller,
    longest waiters first. The rest are told they are on the waitlist and move to the front next week."""
    admitted, deferred = [], []
    for city in sorted({u.city for u in live}):
        here = [u for u in live if u.city == city]
        men = [u for u in here if u.gender == "man"]
        women = [u for u in here if u.gender == "woman"]
        others = [u for u in here if u.gender not in ("man", "woman")]
        big, small = (men, women) if len(men) >= len(women) else (women, men)
        cap = int(math.ceil(len(small) * ADMIT_SLACK)) if small else 0
        big = sorted(big, key=lambda u: (-u.wait, u.joined_week, rand01(seed, "admit", u.id)))
        admitted += small + others + big[:cap]
        deferred += big[cap:]
    return admitted, deferred


def run_policy(policy: str, params: SimParams, base_users: list[User] | None = None) -> PolicyRun:
    users = copy.deepcopy(base_users) if base_users is not None else base_cohort(params)
    cfg = _cfg(params)
    if policy == "one_shot":
        cfg = replace(cfg, carryover=False)
    run = PolicyRun(policy=policy)
    exposed: set[str] = set()
    engaged: set[str] = set()
    ghost = {"mutuals": 0, "ghosted": 0, "closes": 0, "chronic_intros": 0, "intros": 0}
    person: dict[str, dict] = {}

    def gate(batch: list[User]) -> None:
        if params.trust_gate:
            for u in batch:
                if u.signals and trust.risk(u.signals) >= trust.QUARANTINE_AT:
                    u.active = False

    gate(users)
    for week in range(1, params.weeks + 1):
        if week > 1 and params.inflow_pct > 0:
            k = int(round(params.n * params.inflow_pct))
            fresh = make_cohort(k, seed=params.seed * 100 + week, pct_women=params.pct_women,
                                pct_nonbinary=params.pct_nonbinary, week=week, prefix="n", cities=params.cities,
                                realistic=params.realistic)
            if params.adv_pct > 0:
                fresh += trust.make_adversaries(int(round(k * params.adv_pct)), params.seed, week, "x")
            _prep(fresh, params)
            gate(fresh)
            users.extend(fresh)
        live_all = [u for u in users if u.active]
        deferred: list[User] = []
        live = live_all
        if params.admission:
            live, deferred = _admit(live_all, params.seed)
        m = compat.build(live)
        if policy == "greedy":
            order = sorted(range(len(live)), key=lambda i: rand01(params.seed, "order", week, live[i].id))
            res = run_greedy(m, cfg, order, week)
        else:
            res = run_matching(m, cfg, week)
        ceil, unreach = _ceiling(m, cfg) if params.ceiling else (0.0, 0.0)

        by_id = {u.id: u for u in live}
        matched_ids: set[str] = set()
        mutual = 0
        to_remove: set[str] = set()
        for it in res.intros:
            a, b = by_id[it.a], by_id[it.b]
            matched_ids.update((a.id, b.id))
            yes_a = a.adversary is not None or rand01(params.seed, "yes", week, a.id) < p_yes(it.a_to_b)
            yes_b = b.adversary is not None or rand01(params.seed, "yes", week, b.id) < p_yes(it.b_to_a)
            for bad, real, real_yes in ((a, b, yes_b), (b, a, yes_a)):
                if bad.adversary and not real.adversary:
                    exposed.add(real.id)
                    if real_yes:
                        engaged.add(real.id)
                    if params.reports and rand01(params.seed, "report", week, real.id) < trust.REPORT_PROB:
                        to_remove.add(bad.id)
            a.history.add(b.id)
            b.history.add(a.id)
            a.wait = b.wait = 0
            if yes_a and yes_b:
                mutual += 1
                if params.ghosting and not (a.adversary or b.adversary):
                    ghost["mutuals"] += 1
                    ghost["chronic_intros"] += int(a.ghosts >= 2 or b.ghosts >= 2)
                    limbo = False
                    for u in (a, b):
                        if rand01(params.seed, "ghost", week, u.id) < u.ghost_prob:
                            if params.closure and rand01(params.seed, "close", week, u.id) < CLOSE_RATE:
                                ghost["closes"] += 1
                            else:
                                u.ghosts += 1
                                limbo = True
                    ghost["ghosted"] += int(limbo)
        ghost["intros"] += len(res.intros)
        for un in res.unmatched:
            by_id[un.id].wait += 1
        for u in deferred:
            u.wait += 1
        for uid in to_remove:
            by_id[uid].active = False
        run.all_scores.extend(it.score for it in res.intros)

        # who was served, for fairness and the promise ledger
        for u in live_all:
            if u.adversary:
                continue
            rec = person.setdefault(u.id, {"gender": u.gender, "weeks": 0, "intros": 0, "cur": 0, "max_drought": 0})
            rec["weeks"] += 1
            if u.id in matched_ids:
                rec["intros"] += 1
                rec["cur"] = 0
            else:
                rec["cur"] += 1
                rec["max_drought"] = max(rec["max_drought"], rec["cur"])

        # people who keep waiting drift away
        left = 0
        for u in live_all:
            if u.wait > 0 and not u.adversary and rand01(params.seed, "churn", week, u.id) < CHURN_PER_WAIT * min(u.wait, 4):
                u.active = False
                left += 1
        pool = len(live)
        scores = [it.score for it in res.intros]
        mism = [abs(by_id[it.a].intent - by_id[it.b].intent) == 1 for it in res.intros]
        run.rows.append(WeekRow(
            week=week, pool=pool, intros=len(res.intros),
            covered=2 * len(res.intros) / pool if pool else 0.0,
            avg_score=float(np.mean(scores)) if scores else 0.0,
            strong_share=float(np.mean([it.tier == "Strong" for it in res.intros])) if res.intros else 0.0,
            mutual_per_100=100.0 * mutual / pool if pool else 0.0,
            waited_2plus=sum(1 for u in live_all if u.wait >= 2) / len(live_all) if live_all else 0.0,
            left=left,
            intent_mismatch=float(np.mean(mism)) if mism else 0.0,
            waitlisted=len(deferred),
            covered_all=2 * len(res.intros) / len(live_all) if live_all else 0.0,
            ceiling=ceil, unreachable=unreach))
        if week == params.weeks:
            run.supply = supply_gaps(m, res.unmatched)
            counts: dict[str, int] = {}
            for un in res.unmatched:
                counts[un.reason] = counts.get(un.reason, 0) + 1
            run.unmatched_reasons = counts
    real = [u for u in users if not u.adversary]
    run.total_joined = len(real)
    run.final_active = sum(1 for u in real if u.active)
    run.retention = run.final_active / run.total_joined if run.total_joined else 0.0
    run.person = [{"id": k, **v} for k, v in person.items()]
    if params.adv_pct > 0:
        ev = trust.evaluate(users)
        run.trust = {**ev, "adversaries": sum(1 for u in users if u.adversary), "real_people": len(real),
                     "exposed": len(exposed), "engaged": len(engaged),
                     "exposed_rate": len(exposed) / len(real) if real else 0.0,
                     "engaged_rate": len(engaged) / len(real) if real else 0.0}
    if params.ghosting:
        run.ghost = {**ghost,
                     "ghost_rate": ghost["ghosted"] / ghost["mutuals"] if ghost["mutuals"] else 0.0,
                     "close_rate": ghost["closes"] / ghost["mutuals"] if ghost["mutuals"] else 0.0,
                     "chronic_share": ghost["chronic_intros"] / ghost["mutuals"] if ghost["mutuals"] else 0.0}
    return run


def compare(params: SimParams) -> dict[str, PolicyRun]:
    base = base_cohort(params)
    return {p: run_policy(p, params, base) for p in POLICIES}


def frontier(params: SimParams, floors: list[float]) -> list[dict]:
    """Quality versus coverage as the floor moves, for the Weekly Drop policy."""
    base = base_cohort(params)
    out = []
    for f in floors:
        run = run_policy("weekly_drop", replace(params, floor=f), base)
        rows = run.rows
        out.append({
            "floor": f,
            "covered": float(np.mean([r.covered for r in rows])),
            "avg_score": float(np.mean(run.all_scores)) if run.all_scores else 0.0,
            "retention": run.retention,
        })
    return out
