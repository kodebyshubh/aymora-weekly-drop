"""Synthetic people for the demo pool and the simulator. Nobody here is real."""
from __future__ import annotations

import hashlib
import random

from .models import User
from .traits import CAMPUS_WEIGHTS, CAMPUSES, GROUPS, HUMOR_TYPES, INTERESTS, OTHER_COLLEGE, SCALE_DIMS

MEN = ["Aarav", "Vivaan", "Kabir", "Ishaan", "Rohan", "Arjun", "Dev", "Neil", "Karan", "Yash",
       "Aditya", "Rahul", "Siddharth", "Varun", "Kunal", "Mihir", "Tanmay", "Rishi", "Samar", "Ayaan"]
WOMEN = ["Anaya", "Diya", "Meera", "Isha", "Kiara", "Riya", "Tara", "Naina", "Aisha", "Sanya",
         "Prisha", "Myra", "Ira", "Zoya", "Aditi", "Kavya", "Nisha", "Pooja", "Shreya", "Trisha"]
NONBINARY = ["Ari", "Kai", "Sasha", "Rey", "Noor", "Jules"]
SURNAMES = ["Sharma", "Iyer", "Rao", "Nair", "Mehta", "Gupta", "Reddy", "Menon", "Kapoor", "Bose",
            "Shah", "Pillai", "Verma", "Joshi", "Das", "Khan", "Singh", "Patel", "Kulkarni", "Chopra"]

# name, trait means, humor options, interests (probability of each), bios
ARCHETYPES = [
    {"key": "cozy_planner",
     "traits": dict(energy=.2, spontaneity=.2, chronotype=.3, openness=.5, conflict=.6, reply_style=.5,
                    ambition=.5, family=.7, tradition=.6, money=.3),
     "humor": ["dry", "wholesome"],
     "interests": ["books", "cooking", "movies", "board games", "coffee", "pets"],
     "bios": ["Has a spreadsheet for the trip and a backup for the backup.",
              "Best evenings involve a blanket and a very long series."]},
    {"key": "social_spark",
     "traits": dict(energy=.85, spontaneity=.75, chronotype=.75, openness=.8, conflict=.7, reply_style=.85,
                    ambition=.6, family=.5, tradition=.25, money=.7),
     "humor": ["goofy", "referential"],
     "interests": ["live gigs", "dance", "travel", "food", "stand-up comedy", "fashion"],
     "bios": ["Will find the best street food within ten minutes of landing anywhere.",
              "Says yes first and checks the calendar later."]},
    {"key": "builder",
     "traits": dict(energy=.45, spontaneity=.4, chronotype=.8, openness=.35, conflict=.5, reply_style=.35,
                    ambition=.9, family=.45, tradition=.3, money=.5),
     "humor": ["dry", "referential"],
     "interests": ["startups", "coding", "gaming", "finance", "coffee", "anime"],
     "bios": ["Ships on weekends and calls it relaxing.",
              "Always building something. Currently trying to build a social life."]},
    {"key": "trail_soul",
     "traits": dict(energy=.6, spontaneity=.65, chronotype=.2, openness=.6, conflict=.5, reply_style=.45,
                    ambition=.45, family=.5, tradition=.35, money=.35),
     "humor": ["wholesome", "goofy"],
     "interests": ["trekking", "running", "photography", "travel", "birdwatching", "fitness"],
     "bios": ["Up before the sun, mostly to be somewhere with a view.",
              "Happiest on a trail with no signal."]},
    {"key": "old_soul",
     "traits": dict(energy=.35, spontaneity=.25, chronotype=.25, openness=.45, conflict=.35, reply_style=.4,
                    ambition=.55, family=.9, tradition=.85, money=.25),
     "humor": ["wholesome", "dry"],
     "interests": ["music", "books", "cooking", "theatre", "volunteering", "cricket"],
     "bios": ["Family dinners, old songs, and a strong opinion about filter coffee.",
              "Believes in calling people, not just texting them."]},
    {"key": "quiet_creative",
     "traits": dict(energy=.3, spontaneity=.6, chronotype=.7, openness=.7, conflict=.4, reply_style=.3,
                    ambition=.5, family=.5, tradition=.35, money=.45),
     "humor": ["sarcastic", "dry"],
     "interests": ["art", "anime", "books", "photography", "music", "movies", "theatre"],
     "bios": ["Sketches in the margins of everything.",
              "Replies slowly, thinks deeply, and means every word."]},
    {"key": "matchday_friend",
     "traits": dict(energy=.75, spontaneity=.55, chronotype=.6, openness=.55, conflict=.65, reply_style=.7,
                    ambition=.55, family=.65, tradition=.5, money=.6),
     "humor": ["goofy", "sarcastic"],
     "interests": ["cricket", "football", "fitness", "food", "gaming", "movies"],
     "bios": ["Group chat admin. Match day is a personality trait.",
              "Will talk you out of overthinking and into dinner."]},
]

CITY_MIX = [("Bengaluru", 0.60), ("Mumbai", 0.15), ("Delhi", 0.15), ("Pune", 0.10)]


def _clip(x: float) -> float:
    return max(0.02, min(0.98, x))


def make_user(rng: random.Random, uid: str, gender: str, week: int = 0,
              cities: list[tuple[str, float]] | None = None) -> User:
    arch = rng.choice(ARCHETYPES)
    traits = {d: round(_clip(rng.gauss(arch["traits"][d], 0.14)), 3) for d in SCALE_DIMS}
    humor = [arch["humor"][0] if rng.random() < 0.7 else arch["humor"][1]]
    if rng.random() < 0.6:
        extra = rng.choice(HUMOR_TYPES)
        if extra != humor[0]:
            humor.append(extra)
    interests = [t for t in arch["interests"] if rng.random() < 0.55]
    interests += [t for t in INTERESTS if t not in interests and rng.random() < 0.04]
    if not interests:
        interests = [rng.choice(arch["interests"])]

    pool = {"man": MEN, "woman": WOMEN, "nonbinary": NONBINARY}[gender]
    name = f"{rng.choice(pool)} {rng.choice(SURNAMES)[0]}."

    if gender == "man":
        seeking = ["woman"] if rng.random() < 0.91 else (["man"] if rng.random() < 0.6 else ["woman", "man", "nonbinary"])
    elif gender == "woman":
        seeking = ["man"] if rng.random() < 0.92 else (["woman"] if rng.random() < 0.6 else ["woman", "man", "nonbinary"])
    else:
        seeking = ["woman", "man", "nonbinary"]

    age = int(round(min(32, max(19, rng.gauss(23.5, 2.4)))))
    age_min = max(18, age - rng.randint(2, 5))
    age_max = min(45, age + rng.randint(2, 6))
    cities = cities or CITY_MIX
    r, acc, city = rng.random(), 0.0, cities[-1][0]
    for c, p in cities:
        acc += p
        if r <= acc:
            city = c
            break
    intent = rng.choices([0, 1, 2], weights=[0.2, 0.45, 0.35])[0]
    priorities = rng.sample(GROUPS, 2)
    return User(
        id=uid, name=name, gender=gender, seeking=seeking, age=age, age_min=age_min, age_max=age_max,
        city=city, open_distance=rng.random() < 0.15, intent=intent, traits=traits, humor=humor,
        interests=sorted(interests), priorities=priorities, bio=rng.choice(arch["bios"]),
        synthetic=True, joined_week=week,
    )


def _u01(seed: int, *parts) -> float:
    h = hashlib.sha256(("|".join(str(p) for p in (seed, *parts))).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def add_realism(u: User, seed: int) -> None:
    """Stated deal-breakers, drawn from a separate hash stream so the base cohort never changes."""
    women, men = u.gender == "woman", u.gender == "man"
    bengaluru = u.city == "Bengaluru"
    if _u01(seed, u.id, "ver") < (0.55 if bengaluru else 0.40):
        if bengaluru:
            r, acc = _u01(seed, u.id, "campus"), 0.0
            u.campus = CAMPUSES[-1]
            for name, w in zip(CAMPUSES, CAMPUS_WEIGHTS):
                acc += w
                if r <= acc:
                    u.campus = name
                    break
        else:
            u.campus = OTHER_COLLEGE
    u.private = _u01(seed, u.id, "priv") < (0.22 if women else 0.06 if men else 0.10)
    u.verified_only = _u01(seed, u.id, "vonly") < (0.18 if women else 0.05)
    u.strict_intent = _u01(seed, u.id, "strict") < 0.22


def make_cohort(n: int, seed: int = 7, pct_women: float = 0.46, pct_nonbinary: float = 0.02,
                week: int = 0, prefix: str = "s", cities: list[tuple[str, float]] | None = None,
                realistic: bool = False) -> list[User]:
    rng = random.Random(seed)
    users = []
    for i in range(n):
        r = rng.random()
        gender = "woman" if r < pct_women else ("nonbinary" if r < pct_women + pct_nonbinary else "man")
        u = make_user(rng, f"{prefix}{week}-{i}", gender, week, cities)
        if realistic:
            add_realism(u, seed)
        users.append(u)
    return users
