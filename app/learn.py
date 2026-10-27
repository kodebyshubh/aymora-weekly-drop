"""Feedback loop: what someone says about an introduction changes next week's weights, only theirs."""
from __future__ import annotations

from .models import User
from .traits import GROUP_SHORT, GROUPS

MULT_MIN, MULT_MAX = 0.6, 1.6
STRONG_GROUP = 0.80


def _bump(user: User, group: str, factor: float) -> None:
    cur = user.weight_mult.get(group, 1.0)
    user.weight_mult[group] = max(MULT_MIN, min(MULT_MAX, cur * factor))


def apply_feedback(user: User, group_scores: dict[str, float], rating: str, reason: str | None) -> str | None:
    """rating: great | fine | no. reason: a compatibility group, only used with 'no'.

    great  -> groups where this pair scored strongly count a little more for this person
    no     -> if they name what felt off, that group counts more (they care about it more than assumed)
    fine   -> no change
    Returns a sentence describing what changed, or None.
    """
    if rating == "great":
        strong = [g for g in GROUPS if group_scores.get(g, 0.0) >= STRONG_GROUP]
        for g in strong:
            _bump(user, g, 1.05)
        if strong:
            names = " and ".join(GROUP_SHORT[g] for g in strong[:2])
            return f"Noted. Your next drop leans a little more on {names}."
        return None
    if rating == "no" and reason in GROUPS:
        _bump(user, reason, 1.2)
        return f"Noted. Your next drop will weigh {GROUP_SHORT[reason]} more."
    return None
