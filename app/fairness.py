"""Attention inequality: who gets introduced, and how unevenly.

For the matching policies attention is introductions per week in the pool. For the swipe-feed baseline it is
expected likes received. The swipe-feed model is an illustration of an app that ranks everyone by
popularity and shows each user the top of the feed. Its Gini depends on the feed size and the popularity
weight chosen here, so read it as a shape, not a measurement of any real app.
"""
from __future__ import annotations

import warnings

import numpy as np

from . import compat

FEED_SIZE = 15
POPULARITY_WEIGHT = 0.6


def gini(x) -> float:
    a = np.sort(np.asarray(x, dtype=float))
    a = a[np.isfinite(a)]
    if a.size == 0 or a.sum() <= 0:
        return 0.0
    n = a.size
    idx = np.arange(1, n + 1)
    return float((2 * (idx * a).sum()) / (n * a.sum()) - (n + 1) / n)


def lorenz(x, points: int = 11) -> list[list[float]]:
    a = np.sort(np.asarray(x, dtype=float))
    if a.size == 0 or a.sum() <= 0:
        return [[0.0, 0.0], [1.0, 1.0]]
    c = np.concatenate([[0.0], np.cumsum(a) / a.sum()])
    xs = np.linspace(0, 1, a.size + 1)
    q = np.linspace(0, 1, points)
    return [[float(t), float(np.interp(t, xs, c))] for t in q]


def person_summary(stats: list[dict]) -> dict:
    """stats: one dict per person with gender, weeks (in pool), intros, max_drought."""
    out: dict = {}
    for key, pick in (("all", None), ("woman", "woman"), ("man", "man")):
        rows = [s for s in stats if s["weeks"] >= 3 and (pick is None or s["gender"] == pick)]
        if not rows:
            out[key] = {"people": 0, "rate": 0.0, "gini": 0.0, "zero_share": 0.0, "kept_once": 0.0, "p95_drought": 0}
            continue
        rate = [s["intros"] / s["weeks"] for s in rows]
        out[key] = {
            "people": len(rows),
            "rate": float(np.mean(rate)),
            "gini": gini(rate),
            "zero_share": float(np.mean([s["intros"] == 0 for s in rows])),
            "kept_once": float(np.mean([s["intros"] > 0 for s in rows])),
            "p95_drought": int(np.percentile([s["max_drought"] for s in rows], 95)),
            "lorenz": lorenz(rate),
        }
    return out


def swipe_feed(users, seed: int = 0) -> dict:
    """Expected likes received if every user is shown the top of a popularity-ranked feed."""
    from .sim import p_yes

    m = compat.build(users)
    n = len(users)
    elig = m.eligible
    d = m.directional
    pop = np.where(elig, d, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pop_j = np.nanmean(pop, axis=0)
    pop_j = np.nan_to_num(pop_j, nan=0.0)
    z = (pop_j - pop_j.mean()) / (pop_j.std() or 1.0)
    feed_score = np.where(elig, d + POPULARITY_WEIGHT * 0.1 * z[None, :], -np.inf)
    likes_in = np.zeros(n)
    k = min(FEED_SIZE, n - 1)
    for i in range(n):
        row = feed_score[i]
        if not np.isfinite(row).any():
            continue
        top = np.argpartition(-row, k)[:k]
        for j in top:
            if np.isfinite(row[j]):
                likes_in[j] += p_yes(float(d[i, j]))
    out = {"feed_size": FEED_SIZE}
    for key, pick in (("all", None), ("woman", "woman"), ("man", "man")):
        idx = [i for i, u in enumerate(users) if pick is None or u.gender == pick]
        v = likes_in[idx]
        if v.size == 0:
            continue
        top_dec = np.sort(v)[-max(1, v.size // 10):]
        out[key] = {"people": int(v.size), "gini": gini(v), "mean_inbound": float(v.mean()),
                    "top_decile_inbound": float(top_dec.mean()),
                    "invisible_share": float(np.mean(v < 0.5)), "lorenz": lorenz(v)}
    return out
