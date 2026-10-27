"""The weekly drop: one pool-wide assignment per week.

Why not just rank candidates per person? Because the same few popular people end up proposed to
many users, and the rest get nothing. A weekly assignment lets every person receive at most one
introduction, chosen so that as many people as possible are covered without dropping below a
quality floor, and so that people who missed out last week go to the front of the line.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

import networkx as nx
import numpy as np

from .compat import Matrices
from .models import Intro

TIER_STRONG = 0.78
TIER_GOOD = 0.66


def tier_for(score: float) -> str:
    if score >= TIER_STRONG:
        return "Strong"
    if score >= TIER_GOOD:
        return "Good"
    return "Worth a hello"


@dataclass(frozen=True)
class DropConfig:
    floor: float = 0.62            # quality floor for a first-week introduction
    min_floor: float = 0.55        # guardrail: the floor never relaxes below this
    relax_per_wait: float = 0.03   # floor relaxes by this much per week a person has waited
    coverage_bias: float = 0.35    # added to every candidate edge: higher means more people covered
    wait_boost: float = 0.12       # extra weight per week waited, per person on an edge
    top_k: int = 25                # each person keeps their best K candidate edges (speed)
    carryover: bool = True         # False turns off relaxation and priority for people who waited
    ghost_penalty: float = 0.05    # priority lost per recorded ghosting (capped at 3), for either person


@dataclass
class Unmatched:
    id: str
    reason: str                    # no_eligible | below_floor | outcompeted
    eligible: int
    viable: int


@dataclass
class DropResult:
    intros: list[Intro] = field(default_factory=list)
    unmatched: list[Unmatched] = field(default_factory=list)
    pool: int = 0


def _candidate_mask(m: Matrices, waits: np.ndarray, cfg: DropConfig) -> np.ndarray:
    if cfg.carryover:
        wmax = np.maximum(waits[:, None], waits[None, :])
        floor = np.maximum(cfg.min_floor, cfg.floor - cfg.relax_per_wait * wmax)
    else:
        floor = cfg.floor
    return m.eligible & (m.mutual >= floor)


def _edge_weights(m: Matrices, waits: np.ndarray, cfg: DropConfig) -> np.ndarray:
    w = cfg.coverage_bias + m.mutual
    if cfg.carryover:
        w = w + cfg.wait_boost * (waits[:, None] + waits[None, :])
    if cfg.ghost_penalty:
        g = np.array([min(u.ghosts, 3) for u in m.users], dtype=float)
        w = w - cfg.ghost_penalty * (g[:, None] + g[None, :])
    return w


def _prune_top_k(weights: np.ndarray, cand: np.ndarray, k: int) -> np.ndarray:
    n = weights.shape[0]
    if n <= k + 1:
        return cand
    masked = np.where(cand, weights, -np.inf)
    idx = np.argpartition(-masked, k, axis=1)[:, :k]
    keep = np.zeros_like(cand)
    rows = np.arange(n)[:, None]
    keep[rows, idx] = True
    keep &= cand
    return keep | keep.T


def run_matching(m: Matrices, cfg: DropConfig, week: int = 0) -> DropResult:
    """Max-weight matching on the candidate graph (each person gets at most one introduction)."""
    n = len(m.users)
    waits = np.array([u.wait for u in m.users], dtype=float)
    cand = _candidate_mask(m, waits, cfg)
    weights = _edge_weights(m, waits, cfg)
    kept = _prune_top_k(weights, cand, cfg.top_k) & cand

    G = nx.Graph()
    ii, jj = np.where(np.triu(kept, 1))
    G.add_weighted_edges_from((int(i), int(j), int(round(weights[i, j] * 10000))) for i, j in zip(ii, jj))
    pairs = nx.max_weight_matching(G, maxcardinality=False)
    return _finish(m, cfg, week, [(min(a, b), max(a, b)) for a, b in pairs], cand)


def run_greedy(m: Matrices, cfg: DropConfig, order: list[int], week: int = 0) -> DropResult:
    """Baseline: first come first served. Each person in turn takes their best free candidate."""
    waits = np.zeros(len(m.users))
    cand = _candidate_mask(m, waits, replace(cfg, carryover=False))
    taken: set[int] = set()
    pairs = []
    for i in order:
        if i in taken:
            continue
        row = np.where(cand[i], m.mutual[i], -1.0)
        for j in taken:
            row[j] = -1.0
        j = int(np.argmax(row))
        if row[j] >= 0:
            taken.update((i, j))
            pairs.append((min(i, j), max(i, j)))
    return _finish(m, cfg, week, pairs, cand)


def _finish(m: Matrices, cfg: DropConfig, week: int, pairs: list[tuple[int, int]], cand: np.ndarray) -> DropResult:
    res = DropResult(pool=int(sum(1 for u in m.users if u.active)))
    matched: set[int] = set()
    for i, j in sorted(pairs):
        a, b = m.users[i], m.users[j]
        s = float(m.mutual[i, j])
        res.intros.append(Intro(a=a.id, b=b.id, score=s, a_to_b=float(m.directional[i, j]),
                                b_to_a=float(m.directional[j, i]), tier=tier_for(s), week=week))
        matched.update((i, j))
    for i, u in enumerate(m.users):
        if not u.active or i in matched:
            continue
        eligible = int(m.eligible[i].sum())
        viable = int(cand[i].sum())
        if eligible == 0:
            reason = "no_eligible"
        elif viable == 0:
            reason = "below_floor"
        else:
            reason = "outcompeted"
        res.unmatched.append(Unmatched(u.id, reason, eligible, viable))
    return res


def supply_gaps(m: Matrices, unmatched: list[Unmatched], top: int = 5) -> list[dict]:
    """Group the people who got nothing by the kind of person who would fix it.

    For each unmatched person, the missing supply is people of the gender(s) they seek, inside their
    age range, in their city. Counting these per segment says where onboarding effort pays off.
    """
    segs: dict[tuple, dict] = {}
    for un in unmatched:
        u = m.users[m.index[un.id]]
        key = (tuple(sorted(u.seeking)), u.city)
        seg = segs.setdefault(key, {"seeking": list(key[0]), "city": key[1], "people": 0, "age_lo": [], "age_hi": [],
                                    "no_eligible": 0, "below_floor": 0, "outcompeted": 0})
        seg["people"] += 1
        seg[un.reason] += 1
        seg["age_lo"].append(u.age_min)
        seg["age_hi"].append(u.age_max)
    out = []
    for seg in segs.values():
        lo = int(np.median(seg.pop("age_lo")))
        hi = int(np.median(seg.pop("age_hi")))
        seg["age_range"] = [lo, hi]
        out.append(seg)
    out.sort(key=lambda s: -s["people"])
    return out[:top]
