"""Compatibility model.

Everything is computed as whole-pool matrices with numpy, so a pool of a thousand people is
scored in well under a second. The pair score is the geometric mean of two directional scores
(how well B fits what A cares about, and the reverse), which keeps one-sided matches out.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import User
from .traits import (
    BALANCED_IDEAL_GAP, CAMPUSES, DIM_GROUP, DIM_IMPORTANCE, DIM_MODE, GENDERS, GROUPS, HUMOR_AFFINITY,
    HUMOR_TYPES, INTERESTS, SCALE_DIMS, SECONDARY_HUMOR_FACTOR, SURVEY, VALUE_DIMS,
)

PRIORITY_BOOST = 1.5          # a group someone named as a top priority counts 1.5x
# Calibration: a raw weighted similarity of 0.66 is what an average random eligible pair scores in
# the reference pool, so it maps to 0.5. Gain 2.0 spreads scores so that the top ~10% sit above 0.75.
CALIB_CENTER = 0.66
CALIB_GAIN = 2.0
VALUES_SHARE = 0.65           # inside "values and interests": values vs shared interests
INTENT_GAP_FACTOR = {0: 1.0, 1: 0.9}


@dataclass
class Matrices:
    users: list[User]
    index: dict[str, int]
    eligible: np.ndarray               # n x n bool, hard filters both ways
    mutual: np.ndarray                 # n x n float, geometric mean of directional scores
    directional: np.ndarray            # n x n float, row = whose preferences
    groups: dict[str, np.ndarray]      # n x n float per group (symmetric)
    weights: np.ndarray                # n x 4 personal group weights (normalised)

    def pair(self, a: str, b: str) -> dict:
        i, j = self.index[a], self.index[b]
        return {
            "eligible": bool(self.eligible[i, j]),
            "mutual": float(self.mutual[i, j]),
            "a_to_b": float(self.directional[i, j]),
            "b_to_a": float(self.directional[j, i]),
            "groups": {g: float(self.groups[g][i, j]) for g in GROUPS},
        }


def personal_weights(u: User) -> np.ndarray:
    """Survey prior, boosted for the groups the person says matter most, nudged by feedback."""
    w = np.array([SURVEY[g] for g in GROUPS], dtype=float)
    for k, g in enumerate(GROUPS):
        if g in u.priorities:
            w[k] *= PRIORITY_BOOST
        w[k] *= u.weight_mult.get(g, 1.0)
    return w / w.sum()


def interest_idf(users: list[User]) -> dict[str, float]:
    """Rare shared interests count for more than common ones."""
    n = len(users)
    df = {t: 0 for t in INTERESTS}
    for u in users:
        for t in set(u.interests):
            if t in df:
                df[t] += 1
    return {t: float(np.log((n + 1) / (df[t] + 1)) + 1.0) for t in INTERESTS}


def calibrate(x):
    """Map a raw weighted similarity to the 0..1 score people see."""
    return np.clip(0.5 + (np.asarray(x, dtype=float) - CALIB_CENTER) * CALIB_GAIN, 0.0, 1.0)


def _similar(diff: np.ndarray, mode: str) -> np.ndarray:
    if mode == "balanced":
        s = 1.0 - np.abs(diff - BALANCED_IDEAL_GAP) / (1.0 - BALANCED_IDEAL_GAP)
    else:
        s = 1.0 - diff
    return np.clip(s, 0.0, 1.0)


def dim_similarity(a: User, b: User, dim: str) -> float:
    d = abs(a.traits[dim] - b.traits[dim])
    return float(_similar(np.array(d), DIM_MODE[dim]))


def humor_affinity(a: User, b: User) -> float:
    pa = a.humor[0]
    pb = b.humor[0]
    sa = a.humor[1] if len(a.humor) > 1 else pa
    sb = b.humor[1] if len(b.humor) > 1 else pb
    f = SECONDARY_HUMOR_FACTOR
    return max(
        HUMOR_AFFINITY[(pa, pb)],
        f * HUMOR_AFFINITY[(sa, pb)],
        f * HUMOR_AFFINITY[(pa, sb)],
        f * f * HUMOR_AFFINITY[(sa, sb)],
    )


def build(users: list[User]) -> Matrices:
    n = len(users)
    index = {u.id: i for i, u in enumerate(users)}
    T = np.array([[u.traits[d] for d in SCALE_DIMS] for u in users], dtype=float).reshape(n, len(SCALE_DIMS))

    sims = {}
    for k, d in enumerate(SCALE_DIMS):
        diff = np.abs(T[:, k][:, None] - T[:, k][None, :])
        sims[d] = _similar(diff, DIM_MODE[d])

    def wmean(dims: list[str]) -> np.ndarray:
        tot = sum(DIM_IMPORTANCE[d] for d in dims)
        return sum(DIM_IMPORTANCE[d] * sims[d] for d in dims) / tot

    vibe = wmean([d for d in SCALE_DIMS if DIM_GROUP[d] == "vibe"])
    comm = wmean([d for d in SCALE_DIMS if DIM_GROUP[d] == "communication"])
    values = wmean(VALUE_DIMS)

    # interests: IDF weighted Jaccard, neutral 0.5 when either side listed nothing
    idf = interest_idf(users)
    tag_ix = {t: k for k, t in enumerate(INTERESTS)}
    X = np.zeros((n, len(INTERESTS)))
    for i, u in enumerate(users):
        for t in u.interests:
            if t in tag_ix:
                X[i, tag_ix[t]] = 1.0
    idf_vec = np.array([idf[t] for t in INTERESTS])
    Xw = X * idf_vec
    inter = Xw @ X.T
    tot = Xw.sum(axis=1)
    union = tot[:, None] + tot[None, :] - inter
    with np.errstate(divide="ignore", invalid="ignore"):
        jac = np.where(union > 0, inter / union, 0.5)
    empty = (X.sum(axis=1) == 0)
    jac = np.where(empty[:, None] | empty[None, :], 0.5, jac)
    # Jaccard overlaps are naturally low; stretch so that "a couple in common" reads as good
    interest_score = np.clip(jac * 2.2, 0.0, 1.0)
    values_interests = VALUES_SHARE * values + (1 - VALUES_SHARE) * interest_score

    # humor
    h_ix = {t: k for k, t in enumerate(HUMOR_TYPES)}
    prim = np.array([h_ix[u.humor[0]] for u in users])
    sec = np.array([h_ix[u.humor[1]] if len(u.humor) > 1 else h_ix[u.humor[0]] for u in users])
    A = np.array([[HUMOR_AFFINITY[(a, b)] for b in HUMOR_TYPES] for a in HUMOR_TYPES])
    f = SECONDARY_HUMOR_FACTOR
    humor = np.maximum.reduce([
        A[prim[:, None], prim[None, :]],
        f * A[sec[:, None], prim[None, :]],
        f * A[prim[:, None], sec[None, :]],
        f * f * A[sec[:, None], sec[None, :]],
    ])

    groups = {"vibe": vibe, "communication": comm, "values_interests": values_interests, "humor": humor}

    # directional score: row i is judging column j with i's own weights
    W = np.array([personal_weights(u) for u in users]).reshape(n, len(GROUPS))
    directional = np.zeros((n, n))
    for k, g in enumerate(GROUPS):
        directional += W[:, k][:, None] * groups[g]

    intent = np.array([u.intent for u in users])
    gap = np.abs(intent[:, None] - intent[None, :])
    factor = np.where(gap == 0, INTENT_GAP_FACTOR[0], np.where(gap == 1, INTENT_GAP_FACTOR[1], 0.0))
    directional = directional * factor
    mutual = calibrate(np.sqrt(directional * directional.T))
    directional = calibrate(directional)

    # hard filters, applied both ways
    g_ix = {g: k for k, g in enumerate(GENDERS)}
    gender = np.array([g_ix[u.gender] for u in users])
    seek = np.zeros((n, len(GENDERS)), dtype=bool)
    for i, u in enumerate(users):
        for s in u.seeking:
            seek[i, g_ix[s]] = True
    wants_gender = seek[np.arange(n)[:, None], gender[None, :]]
    age = np.array([u.age for u in users])
    amin = np.array([u.age_min for u in users])
    amax = np.array([u.age_max for u in users])
    wants_age = (age[None, :] >= amin[:, None]) & (age[None, :] <= amax[:, None])
    cities = sorted({u.city for u in users})
    c_ix = {c: k for k, c in enumerate(cities)}
    city = np.array([c_ix[u.city] for u in users])
    open_d = np.array([u.open_distance for u in users])
    place_ok = (city[:, None] == city[None, :]) | (open_d[:, None] & open_d[None, :])
    ok = wants_gender & wants_age
    eligible = ok & ok.T & place_ok & (gap <= 1)
    np.fill_diagonal(eligible, False)

    # stated deal-breakers: exact intent, hidden from my own college circle, campus-verified only
    strict = np.array([u.strict_intent for u in users])
    eligible &= ~((strict[:, None] | strict[None, :]) & (gap != 0))
    c_id = np.array([CAMPUSES.index(u.campus) if u.campus in CAMPUSES else -1 for u in users])
    private = np.array([u.private for u in users])
    same_circle = (c_id[:, None] == c_id[None, :]) & (c_id[:, None] >= 0)
    eligible &= ~((private[:, None] | private[None, :]) & same_circle)
    verified = np.array([bool(u.campus) for u in users])
    v_only = np.array([u.verified_only for u in users])
    eligible &= ~((v_only[:, None] & ~verified[None, :]) | (v_only[None, :] & ~verified[:, None]))

    # never repeat an introduction
    for i, u in enumerate(users):
        for hid in u.history:
            j = index.get(hid)
            if j is not None:
                eligible[i, j] = False
                eligible[j, i] = False

    # inactive people are not in this week's pool
    active = np.array([u.active for u in users])
    eligible &= active[:, None] & active[None, :]

    return Matrices(users, index, eligible, mutual, directional, groups, W)
