"""Trait model for Weekly Drop.

Four compatibility groups mirror what Aymora's own on-ground survey (2,354 daters, 12 cities)
says matters most. Physical appearance (27%) is deliberately left out of matching in v1.
"""
from __future__ import annotations

GROUPS = ["vibe", "communication", "values_interests", "humor"]

GROUP_LABEL = {
    "vibe": "Vibe and personality",
    "communication": "Communication",
    "values_interests": "Values and interests",
    "humor": "Humor",
}

# Aymora survey results, percent of daters who said the thing matters most.
SURVEY = {"vibe": 73.0, "communication": 64.0, "values_interests": 48.0, "humor": 42.0}
SURVEY_PHYSICAL_APPEARANCE = 27.0  # not used by the engine

SCALE_DIMS = [
    "energy", "spontaneity", "chronotype",
    "openness", "conflict", "reply_style",
    "ambition", "family", "tradition", "money",
]

DIM_GROUP = {
    "energy": "vibe", "spontaneity": "vibe", "chronotype": "vibe",
    "openness": "communication", "conflict": "communication", "reply_style": "communication",
    "ambition": "values_interests", "family": "values_interests",
    "tradition": "values_interests", "money": "values_interests",
}

VALUE_DIMS = ["ambition", "family", "tradition", "money"]

# "balanced" means a little difference is a plus (a planner and an improviser balance out).
DIM_MODE = {d: "similar" for d in SCALE_DIMS}
DIM_MODE["spontaneity"] = "balanced"
BALANCED_IDEAL_GAP = 0.25

# Some differences hurt more than others.
DIM_IMPORTANCE = {
    "energy": 1.0, "spontaneity": 0.9, "chronotype": 0.7,
    "openness": 1.0, "conflict": 1.4, "reply_style": 0.8,
    "ambition": 1.0, "family": 1.3, "tradition": 1.3, "money": 0.8,
}

DIM_NAME = {
    "energy": "social energy", "spontaneity": "planning style", "chronotype": "daily rhythm",
    "openness": "how you share feelings", "conflict": "how you handle disagreements",
    "reply_style": "texting rhythm", "ambition": "drive", "family": "family closeness",
    "tradition": "tradition", "money": "spending style",
}

# (low end phrase, high end phrase). Written so they read right after "You both", "You ..." and "they ...".
DIM_PHRASE = {
    "energy": ("recharge best at home", "like plans out of the house"),
    "spontaneity": ("like to plan ahead", "prefer to improvise"),
    "chronotype": ("are early birds", "run on night owl hours"),
    "openness": ("keep feelings close until trust is there", "share feelings openly"),
    "conflict": ("need a breather before a hard conversation", "would rather talk it out right away"),
    "reply_style": ("text when there is something to say", "keep the conversation going through the day"),
    "ambition": ("value an unhurried life", "are driven to build something"),
    "family": ("keep life independent", "keep family close"),
    "tradition": ("lean modern about how life should look", "value tradition"),
    "money": ("are savers", "enjoy spending on good experiences"),
}

# ---- humor -----------------------------------------------------------------------------------
HUMOR_TYPES = ["dry", "goofy", "sarcastic", "wholesome", "referential"]
HUMOR_NAME = {
    "dry": "dry and deadpan", "goofy": "goofy", "sarcastic": "sarcastic",
    "wholesome": "warm and wholesome", "referential": "movie and meme reference heavy",
}
HUMOR_SHORT = {"dry": "dry", "goofy": "goofy", "sarcastic": "sarcastic", "wholesome": "wholesome",
               "referential": "reference-heavy"}
GROUP_SHORT = {"vibe": "vibe", "communication": "communication",
               "values_interests": "values and interests", "humor": "humor"}
_H = {
    ("dry", "dry"): 1.0, ("goofy", "goofy"): 1.0, ("sarcastic", "sarcastic"): 0.9,
    ("wholesome", "wholesome"): 1.0, ("referential", "referential"): 1.0,
    ("dry", "sarcastic"): 0.85, ("dry", "referential"): 0.75, ("dry", "goofy"): 0.45,
    ("dry", "wholesome"): 0.55, ("goofy", "wholesome"): 0.85, ("goofy", "referential"): 0.70,
    ("goofy", "sarcastic"): 0.50, ("sarcastic", "referential"): 0.70,
    ("sarcastic", "wholesome"): 0.35, ("referential", "wholesome"): 0.55,
}
HUMOR_AFFINITY = {}
for (_a, _b), _v in _H.items():
    HUMOR_AFFINITY[(_a, _b)] = _v
    HUMOR_AFFINITY[(_b, _a)] = _v
SECONDARY_HUMOR_FACTOR = 0.92

# ---- interests -------------------------------------------------------------------------------
INTERESTS = [
    "music", "live gigs", "anime", "gaming", "fitness", "running", "cricket", "football",
    "travel", "trekking", "food", "cooking", "coffee", "books", "movies", "stand-up comedy",
    "photography", "art", "dance", "startups", "coding", "finance", "fashion", "pets",
    "birdwatching", "board games", "theatre", "volunteering",
]

# Keyword hints used to pull interests out of free text when no LLM is configured.
INTEREST_KEYWORDS = {
    "music": ["music", "playlist", "guitar", "singing", "spotify"],
    "live gigs": ["gig", "concert", "live music"],
    "anime": ["anime", "manga"],
    "gaming": ["gaming", "gamer", "valorant", "pubg", "playstation", "console"],
    "fitness": ["gym", "workout", "fitness", "lifting"],
    "running": ["running", "marathon", "5k", "10k"],
    "cricket": ["cricket", "ipl"],
    "football": ["football", "soccer"],
    "travel": ["travel", "trip", "backpack", "roadtrip", "road trip"],
    "trekking": ["trek", "hike", "hiking", "trail"],
    "food": ["food", "foodie", "restaurant", "street food", "biryani"],
    "cooking": ["cook", "baking", "bake", "kitchen"],
    "coffee": ["coffee", "cafe", "chai"],
    "books": ["book", "reading", "novel"],
    "movies": ["movie", "film", "cinema", "netflix", "series"],
    "stand-up comedy": ["stand-up", "standup", "comedy"],
    "photography": ["photo", "camera"],
    "art": ["art", "sketch", "painting", "drawing"],
    "dance": ["dance", "dancing"],
    "startups": ["startup", "founder", "build something"],
    "coding": ["coding", "code", "programming", "hackathon"],
    "finance": ["stocks", "investing", "finance", "markets"],
    "fashion": ["fashion", "thrift", "style"],
    "pets": ["dog", "cat", "pet"],
    "birdwatching": ["bird"],
    "board games": ["board game", "chess", "cards"],
    "theatre": ["theatre", "theater", "play", "drama"],
    "volunteering": ["volunteer", "ngo", "community service"],
}

INTENT_LABEL = {0: "keeping it casual", 1: "open to something long term", 2: "looking for something serious"}

GENDERS = ["man", "woman", "nonbinary"]

# Campus circles. Family-privacy mode hides you from people in your own circle. Verification is mocked
# in this prototype: a real build would check a .ac.in or .edu.in email.
CAMPUSES = ["DSCE", "PES University", "RVCE", "BMSCE", "Christ University", "MSRIT", "IIIT Bangalore"]
CAMPUS_WEIGHTS = [0.25, 0.20, 0.15, 0.12, 0.10, 0.10, 0.08]
OTHER_COLLEGE = "Other college"
