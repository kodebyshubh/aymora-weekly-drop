"""Trust: synthetic scam agents for red-team runs, and a transparent risk score.

The score is a hand-set logistic over signals a real product could see before anyone is matched:
account age, copy-pasted bios across accounts, contact details or money talk in the bio, an email domain
that does not match the claimed college, prior reports, and a reverse-image hit on the photo.
Benign people trip these signals too (plenty of honest people put an Instagram handle in their bio),
so the score is not perfect, and the red-team report shows what that costs in wrongly held-back people.
"""
from __future__ import annotations

import hashlib
import math
import random

from .cohort import make_user
from .models import User

QUARANTINE_AT = 0.60       # held back before matching
WATCH_AT = 0.35            # still matched, but the other person sees a caution banner
REPORT_PROB = 0.25          # assumption: share of real people who report a scammer they were introduced to
KINDS = ["bot", "romance_scammer", "sextortion", "ring"]
KIND_LABEL = {"bot": "Bot", "romance_scammer": "Romance scammer", "sextortion": "Sextortion", "ring": "Fake-profile ring"}

# probability of each signal by kind: (new account, offplatform, money, email mismatch, reuse, reported, dupes)
_ADV = {
    "bot":             dict(new=0.90, off=0.60, money=0.20, mismatch=0.50, reuse=0.50, reported=0.20, dupe=(0.70, 3, 30)),
    "romance_scammer": dict(new=0.70, off=0.90, money=0.70, mismatch=0.40, reuse=0.70, reported=0.30, dupe=(0.20, 1, 4)),
    "sextortion":      dict(new=0.80, off=0.90, money=0.30, mismatch=0.50, reuse=0.60, reported=0.25, dupe=(0.10, 1, 3)),
    "ring":            dict(new=0.60, off=0.50, money=0.40, mismatch=0.50, reuse=0.50, reported=0.15, dupe=(0.90, 5, 20)),
}


def _u01(seed: int, *parts) -> float:
    h = hashlib.sha256(("|".join(str(p) for p in (seed, *parts))).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def benign_signals(seed: int, uid: str) -> dict:
    new = _u01(seed, uid, "new") < 0.12
    return {
        "account_age_days": int(1 + _u01(seed, uid, "age") * 6) if new else int(8 + _u01(seed, uid, "age") ** 2 * 400),
        "bio_dupe": 1 if _u01(seed, uid, "dupe") < 0.04 else 0,
        "offplatform_bio": int(_u01(seed, uid, "off") < 0.08),
        "money_words": int(_u01(seed, uid, "money") < 0.03),
        "email_mismatch": int(_u01(seed, uid, "mm") < 0.04),
        "prior_reports": int(_u01(seed, uid, "rep") < 0.01),
        "photo_reuse": int(_u01(seed, uid, "reuse") < 0.015),
    }


def adversary_signals(seed: int, uid: str, kind: str) -> dict:
    p = _ADV[kind]
    new = _u01(seed, uid, "new") < p["new"]
    dupe_p, lo, hi = p["dupe"]
    dupe = int(lo + _u01(seed, uid, "dupen") * (hi - lo)) if _u01(seed, uid, "dupe") < dupe_p else 0
    return {
        "account_age_days": int(1 + _u01(seed, uid, "age") * 6) if new else int(8 + _u01(seed, uid, "age") * 40),
        "bio_dupe": dupe,
        "offplatform_bio": int(_u01(seed, uid, "off") < p["off"]),
        "money_words": int(_u01(seed, uid, "money") < p["money"]),
        "email_mismatch": int(_u01(seed, uid, "mm") < p["mismatch"]),
        "prior_reports": int(_u01(seed, uid, "rep") < p["reported"]),
        "photo_reuse": int(_u01(seed, uid, "reuse") < p["reuse"]),
    }


def risk(signals: dict) -> float:
    s = signals
    z = (-4.0
         + 1.6 * (s.get("account_age_days", 365) < 7)
         + 0.35 * min(s.get("bio_dupe", 0), 6)
         + 1.5 * s.get("offplatform_bio", 0)
         + 1.7 * s.get("money_words", 0)
         + 1.1 * s.get("email_mismatch", 0)
         + 1.2 * min(s.get("prior_reports", 0), 2)
         + 1.8 * s.get("photo_reuse", 0))
    return 1.0 / (1.0 + math.exp(-z))


def reasons(signals: dict) -> list[str]:
    s, out = signals, []
    if s.get("account_age_days", 365) < 7:
        out.append("account is under a week old")
    if s.get("bio_dupe", 0) >= 2:
        out.append("bio is copied across other accounts")
    if s.get("offplatform_bio"):
        out.append("bio pushes contact off the app")
    if s.get("money_words"):
        out.append("bio talks about money or investing")
    if s.get("email_mismatch"):
        out.append("email domain does not match the college")
    if s.get("prior_reports"):
        out.append("already reported by someone")
    if s.get("photo_reuse"):
        out.append("photo appears elsewhere online")
    return out


def attach_signals(users: list[User], seed: int) -> None:
    for u in users:
        if not u.signals:
            u.signals = benign_signals(seed, u.id)


def make_adversaries(k: int, seed: int, week: int = 0, prefix: str = "x") -> list[User]:
    """Fake profiles that look like ordinary people: most pose as women looking for men."""
    rng = random.Random(seed * 7919 + week)
    out = []
    for i in range(k):
        uid = f"{prefix}{week}-{i}"
        gender = "woman" if rng.random() < 0.7 else "man"
        u = make_user(rng, uid, gender, week)
        u.seeking = ["man"] if gender == "woman" else ["woman"]
        u.age = rng.randint(21, 27)
        u.age_min, u.age_max = max(18, u.age - 3), u.age + 6
        u.intent = rng.choice([1, 2])
        u.adversary = rng.choice(KINDS)
        u.signals = adversary_signals(seed, uid, u.adversary)
        out.append(u)
    return out


def evaluate(users: list[User]) -> dict:
    """Precision and recall of the quarantine rule over everyone who has signals."""
    tp = fp = fn = tn = 0
    for u in users:
        if not u.signals:
            continue
        flagged = risk(u.signals) >= QUARANTINE_AT
        if u.adversary:
            tp += flagged
            fn += not flagged
        else:
            fp += flagged
            tn += not flagged
    prec = tp / (tp + fp) if tp + fp else 1.0
    rec = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec}


def benchmark(seed: int = 1, honest: int = 3000, scam: int = 200, thresholds=(0.3, 0.4, 0.5, 0.6, 0.7)) -> list[dict]:
    """Precision, recall and wrongly held-back honest people at each threshold, on a larger synthetic sample."""
    h = [risk(benign_signals(seed, f"h{i}")) for i in range(honest)]
    a = [risk(adversary_signals(seed, f"a{i}", KINDS[i % len(KINDS)])) for i in range(scam)]
    out = []
    for t in thresholds:
        tp = sum(r >= t for r in a)
        fp = sum(r >= t for r in h)
        out.append({"threshold": t, "recall": tp / scam, "precision": tp / (tp + fp) if tp + fp else 1.0,
                    "honest_held_back": fp / honest, "honest": honest, "scam": scam})
    return out
