from app.models import User
from app.traits import SCALE_DIMS


def make(uid="u", gender="man", seeking=("woman",), age=24, age_min=20, age_max=30, city="Bengaluru",
         open_distance=False, intent=1, level=0.5, humor=("dry",), interests=("coffee",), **overrides) -> User:
    traits = {d: level for d in SCALE_DIMS}
    fields = {k: overrides.pop(k) for k in ("campus", "private", "strict_intent", "verified_only", "ghosts", "wait",
                                            "signals", "adversary") if k in overrides}
    traits.update(overrides)
    return User(id=uid, name=f"{uid} X.", gender=gender, seeking=list(seeking), age=age, age_min=age_min,
                age_max=age_max, city=city, open_distance=open_distance, intent=intent, traits=traits,
                humor=list(humor), interests=list(interests), priorities=[], **fields)
