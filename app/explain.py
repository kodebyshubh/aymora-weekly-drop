"""Plain-language reasons for every introduction.

Every sentence is built from the two people's own answers, so nothing is invented. A language model
can reword the result (see llm.py) but is never the source of facts.
"""
from __future__ import annotations

from .compat import Matrices, dim_similarity, humor_affinity
from .models import User
from .traits import (
    DIM_GROUP, DIM_IMPORTANCE, DIM_MODE, DIM_NAME, DIM_PHRASE, GROUP_LABEL, GROUPS, HUMOR_SHORT,
    SCALE_DIMS,
)

OPENERS = {
    "music": "What's the song you've had on repeat this month?",
    "live gigs": "Best live show you've ever been to, and would you go again?",
    "anime": "Which anime would you make me watch first, and why?",
    "gaming": "What's the game you'd happily lose a weekend to?",
    "fitness": "What's your favourite workout and your favourite excuse to skip it?",
    "running": "Longest run you've done, and was it worth it?",
    "cricket": "Settle this: which player would you pick for a final over?",
    "football": "Which team broke your heart the hardest?",
    "travel": "Where did you go that you'd send everyone to?",
    "trekking": "Which trail would you do again tomorrow?",
    "food": "What's the one dish you'd cross the city for?",
    "cooking": "What do you cook when you want to impress someone?",
    "coffee": "How do you take your coffee, and will you judge mine?",
    "books": "What book do you keep recommending to people?",
    "movies": "What's a film you can rewatch without getting bored?",
    "stand-up comedy": "Whose stand-up set could you quote word for word?",
    "photography": "What's the best photo you've ever taken?",
    "art": "What's the last thing you made, even badly?",
    "dance": "What song makes it impossible for you to stay seated?",
    "startups": "If you had a free year and a little money, what would you build?",
    "coding": "What's the side project you keep meaning to finish?",
    "finance": "Best money lesson you learned the hard way?",
    "fashion": "What's the piece in your wardrobe with the best story?",
    "pets": "Introduce me to your pet, or the one you wish you had.",
    "birdwatching": "What's the best bird you've ever spotted?",
    "board games": "Which game do you take far too seriously?",
    "theatre": "Best play you've seen, and did it change anything for you?",
    "volunteering": "What's a cause you'd give a whole weekend to?",
}

DATE_IDEAS = {
    "coffee": "a long coffee at a cafe neither of you has tried",
    "food": "a street food crawl where you split everything",
    "trekking": "an easy trail walk with a good view and a flask of chai",
    "running": "a slow Sunday run, then breakfast",
    "books": "an hour in a bookshop, then compare what you picked",
    "movies": "an afternoon show followed by an argument about the ending",
    "live gigs": "a small live gig where the band is better than the venue",
    "stand-up comedy": "an open mic night",
    "photography": "a photo walk through an old part of the city",
    "art": "a gallery visit with a rule: pick the one you'd steal",
    "cooking": "cooking one meal together from whatever is in the fridge",
    "board games": "a board game cafe",
    "music": "a record shop browse, then swap playlists",
    "travel": "a short day trip somewhere neither of you has been",
    "birdwatching": "an early morning walk at a lake or park",
    "gaming": "a gaming cafe, winner pays for dinner",
    "football": "a five-a-side game with friends, then dinner",
    "cricket": "gully cricket, then chai",
}


def _join(items: list[str]) -> str:
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _side(v: float) -> int:
    return 1 if v >= 0.5 else 0


def rare_shared(a: User, b: User, idf: dict[str, float]) -> list[str]:
    shared = [t for t in a.interests if t in b.interests]
    return sorted(shared, key=lambda t: -idf.get(t, 1.0))


def explain_pair(me: User, other: User, m: Matrices, idf: dict[str, float]) -> dict:
    pair = m.pair(me.id, other.id)
    gs = pair["groups"]
    weights = dict(zip(GROUPS, m.weights[m.index[me.id]]))

    # Every possible reason gets a salience: how strongly it holds, times how much this person cares
    # about that part of compatibility. The best ones win, with at most one per group where possible.
    options = []   # (salience, group, text)
    for d in SCALE_DIMS:
        sim = dim_similarity(me, other, d)
        gap = abs(me.traits[d] - other.traits[d])
        g = DIM_GROUP[d]
        salience = sim * DIM_IMPORTANCE[d] * weights[g]
        if DIM_MODE[d] == "balanced":
            if 0.12 <= gap <= 0.45:
                options.append((salience, g, "One of you plans and the other improvises. That balance tends to work."))
        elif sim >= 0.80 and _side(me.traits[d]) == _side(other.traits[d]):
            options.append((salience, g, f"You both {DIM_PHRASE[d][_side(me.traits[d])]}."))

    aff = humor_affinity(me, other)
    if aff >= 0.75:
        if me.humor[0] == other.humor[0]:
            text = f"Your humor lines up: you both lean {HUMOR_SHORT[me.humor[0]]}."
        else:
            text = (f"Different comic styles ({HUMOR_SHORT[me.humor[0]]} meets {HUMOR_SHORT[other.humor[0]]}), "
                    "but they tend to land well together.")
        options.append((aff * weights["humor"] * 1.6, "humor", text))
    shared = rare_shared(me, other, idf)
    if shared:
        text = (f"You both care about {shared[0]}." if len(shared) == 1
                else f"You share {_join(shared[:3])}.")
        options.append((min(1.0, 0.45 + 0.2 * len(shared)) * weights["values_interests"] * 1.6, "values_interests", text))

    options.sort(key=lambda o: -o[0])
    reasons: list[str] = []
    used: set[str] = set()
    for _sal, g, text in options:           # first pass: one reason per group
        if g not in used and len(reasons) < 3:
            reasons.append(text)
            used.add(g)
    for _sal, g, text in options:           # second pass: fill remaining slots
        if text not in reasons and len(reasons) < 3:
            reasons.append(text)
    if not reasons:
        best = max(GROUPS, key=lambda g: gs[g])
        reasons.append(f"Your strongest overlap is {GROUP_LABEL[best].lower()}.")

    # honest watch-out: the biggest gap on something that matters
    watch = None
    worst = None
    for d in SCALE_DIMS:
        if DIM_MODE[d] == "balanced":
            continue
        gap = abs(me.traits[d] - other.traits[d])
        if gap >= 0.45 and (worst is None or gap * DIM_IMPORTANCE[d] > worst[0]):
            worst = (gap * DIM_IMPORTANCE[d], d)
    if worst:
        d = worst[1]
        watch = (f"You differ on {DIM_NAME[d]}: you {DIM_PHRASE[d][_side(me.traits[d])]}, "
                 f"they {DIM_PHRASE[d][_side(other.traits[d])]}. Worth talking about early.")

    opener = OPENERS[shared[0]] if shared else {
        "dry": "What's the most understated thing that has ever made you laugh?",
        "goofy": "What's the worst pun you're secretly proud of?",
        "sarcastic": "Give me your most useless superpower, and defend it.",
        "wholesome": "What's a small thing that made your week better?",
        "referential": "Which movie quote do you use far too often?",
    }[me.humor[0]]

    idea = None
    for t in shared:
        if t in DATE_IDEAS:
            idea = DATE_IDEAS[t]
            break
    if idea is None:
        idea = ("a quiet cafe with good chai and no schedule" if (me.traits["energy"] + other.traits["energy"]) / 2 < 0.5
                else "something lively with a little room for surprises, like a market or a live gig")
    if me.traits["chronotype"] < 0.35 and other.traits["chronotype"] < 0.35:
        idea += ". Make it a morning."
    elif me.traits["chronotype"] > 0.65 and other.traits["chronotype"] > 0.65:
        idea += ". Make it a late one."

    return {
        "reasons": reasons[:3],
        "watch_out": watch,
        "opener": opener,
        "date_idea": idea[0].upper() + idea[1:] + ("" if idea.endswith(".") else "."),
        "shared_interests": shared,
        "groups": {g: round(gs[g], 3) for g in GROUPS},
        "weights": {g: round(float(weights[g]), 3) for g in GROUPS},
    }
