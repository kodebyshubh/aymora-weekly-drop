"""Can the promise be kept? Weekly Drop's "one introduction every week" measured against the best any policy could do.

Three numbers carry the story:
  delivered    the share of the pool that got an introduction this week
  ceiling      the most any policy could deliver (maximum-cardinality matching at the loosest floor)
  unreachable  people with nobody they could ever be introduced to, which no algorithm fixes

The supply curve then asks the founder's question: how many women (or how dense a city) does it take
to keep the promise for 90% of people?
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from . import fairness, trust
from .sim import POLICIES, POLICY_LABEL, SimParams, base_cohort, compare, run_policy

TARGET = 0.90
WOMEN_GRID = [0.30, 0.40, 0.45, 0.50, 0.55, 0.60]


def _avg(rows, key: str) -> float:
    return float(np.mean([getattr(r, key) for r in rows])) if rows else 0.0


def summarize(run) -> dict:
    ps = fairness.person_summary(run.person)
    rows = run.rows
    return {
        "covered": _avg(rows, "covered"),
        "covered_all": _avg(rows, "covered_all"),
        "kept_once": ps["all"]["kept_once"],
        "avg_score": float(np.mean(run.all_scores)) if run.all_scores else 0.0,
        "retention": run.retention,
        "waitlisted_share": float(np.mean([r.waitlisted / max(1, r.pool + r.waitlisted) for r in rows])),
        "waited_2plus": rows[-1].waited_2plus if rows else 0.0,
    }


def _curve(params: SimParams, cities) -> list[dict]:
    short = replace(params, n=min(params.n, 200), weeks=min(params.weeks, 4), cities=cities, ceiling=False)
    out = []
    for w in WOMEN_GRID:
        run = run_policy("weekly_drop", replace(short, pct_women=w), None)
        ps = fairness.person_summary(run.person)
        out.append({"pct_women": w, "covered": _avg(run.rows, "covered"), "kept_once": ps["all"]["kept_once"],
                    "men_kept_once": ps["man"]["kept_once"], "women_kept_once": ps["woman"]["kept_once"]})
    return out


def _window(curve: list[dict]) -> list[float] | None:
    """Range of women's share where coverage reaches TARGET, interpolating between grid points."""
    pts = [(c["pct_women"], c["covered"]) for c in curve]
    ok = [x for x, y in pts if y >= TARGET]
    if not ok:
        return None
    lo, hi = min(ok), max(ok)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y0 < TARGET <= y1 and x0 < lo:
            lo = x0 + (TARGET - y0) / (y1 - y0) * (x1 - x0)
        if y0 >= TARGET > y1 and x1 > hi:
            hi = x0 + (y0 - TARGET) / (y0 - y1) * (x1 - x0)
    return [round(lo, 3), round(hi, 3)]


def promise_report(params: SimParams) -> dict:
    p = replace(params, ceiling=True)
    base = base_cohort(p)
    run = run_policy("weekly_drop", p, base)
    rows = run.rows
    headline = {"delivered": _avg(rows, "covered"), "ceiling": _avg(rows, "ceiling"),
                "unreachable": _avg(rows, "unreachable")}
    headline["gap_to_ceiling"] = max(0.0, headline["ceiling"] - headline["delivered"])
    people = fairness.person_summary(run.person)

    # the three policies and the swipe-feed illustration, on the same people
    flat = replace(p, ceiling=False)
    runs = compare(flat)
    attention = {k: fairness.person_summary(runs[k].person) for k in POLICIES}
    for k in POLICIES:
        for g in attention[k].values():
            g.pop("lorenz", None)
    people_out = {g: {k: v for k, v in d.items() if k != "lorenz"} for g, d in people.items()}
    feed = fairness.swipe_feed([u for u in base if not u.adversary], p.seed)
    for g in ("all", "woman", "man"):
        feed.get(g, {}).pop("lorenz", None)

    levers = []
    variants = [
        ("As launched", {}),
        ("Balanced admission", {"admission": True}),
        ("One city at a time", {"cities": [("Bengaluru", 1.0)]}),
        ("One city plus balanced admission", {"cities": [("Bengaluru", 1.0)], "admission": True}),
    ]
    for name, change in variants:
        r = run_policy("weekly_drop", replace(flat, **change), None)
        levers.append({"name": name, **summarize(r)})

    return {
        "params": {"n": p.n, "weeks": p.weeks, "pct_women": p.pct_women, "floor": p.floor, "seed": p.seed,
                   "one_city": p.cities is not None},
        "weekly": [{"week": r.week, "delivered": r.covered, "ceiling": r.ceiling, "unreachable": r.unreachable,
                    "waited_2plus": r.waited_2plus} for r in rows],
        "headline": headline,
        "people": people_out,
        "attention": attention,
        "swipe": feed,
        "labels": POLICY_LABEL,
        "levers": levers,
        "supply": run.supply,
    }


def curve_report(params: SimParams) -> dict:
    """Promise kept as the share of women moves, for the current city mix and for one city."""
    now = _curve(params, params.cities)
    one = _curve(params, [("Bengaluru", 1.0)])
    return {"current": now, "one_city": one, "window": {"current": _window(now), "one_city": _window(one)},
            "target": TARGET, "grid": WOMEN_GRID}


def redteam_report(params: SimParams, adv_pct: float = 0.05) -> dict:
    p = replace(params, adv_pct=adv_pct, ceiling=False, realistic=False)
    base = base_cohort(p)
    modes = [("No defence", dict(trust_gate=False, reports=False)),
             ("Reports only", dict(trust_gate=False, reports=True)),
             ("Trust gate", dict(trust_gate=True, reports=False)),
             ("Trust gate and reports", dict(trust_gate=True, reports=True))]
    out = []
    for name, change in modes:
        r = run_policy("weekly_drop", replace(p, **change), base)
        t = r.trust
        out.append({"name": name, "exposed_rate": t["exposed_rate"], "engaged_rate": t["engaged_rate"],
                    "exposed": t["exposed"], "real_people": t["real_people"], "precision": t["precision"],
                    "recall": t["recall"], "held_back_real": t["fp"] if change["trust_gate"] else 0,
                    "caught": t["tp"] if change["trust_gate"] else 0, "adversaries": t["adversaries"],
                    "covered": _avg(r.rows, "covered")})
    kinds: dict[str, dict] = {}
    for u in base:
        if u.adversary:
            k = kinds.setdefault(u.adversary, {"kind": u.adversary, "label": trust.KIND_LABEL[u.adversary], "count": 0, "caught": 0})
            k["count"] += 1
            k["caught"] += int(trust.risk(u.signals) >= trust.QUARANTINE_AT)
    return {"params": {"n": p.n, "weeks": p.weeks, "adv_pct": adv_pct, "seed": p.seed,
                       "threshold": trust.QUARANTINE_AT, "report_prob": trust.REPORT_PROB},
            "modes": out, "kinds": list(kinds.values()), "benchmark": trust.benchmark(p.seed)}


def closure_report(params: SimParams) -> dict:
    p = replace(params, ghosting=True, ceiling=False)
    base = base_cohort(p)
    out = []
    for name, closure in (("No closure protocol", False), ("Closure protocol", True)):
        r = run_policy("weekly_drop", replace(p, closure=closure), base)
        g = r.ghost
        out.append({"name": name, "ghost_rate": g["ghost_rate"], "close_rate": g["close_rate"],
                    "chronic_share": g["chronic_share"], "mutuals": g["mutuals"],
                    "reasons_per_100": 100.0 * g["closes"] / g["intros"] if g["intros"] else 0.0,
                    "avg_score": float(np.mean(r.all_scores)) if r.all_scores else 0.0})
    return {"params": {"n": p.n, "weeks": p.weeks, "seed": p.seed}, "modes": out}
