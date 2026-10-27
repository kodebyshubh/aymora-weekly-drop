"""The questionnaire: ten one-tap scenarios, humor, interests, priorities, basics.

Each scenario answer sets one trait to a value between 0 and 1. Under two minutes end to end,
in line with Aymora's "a few thoughtful questions, not a checklist of hobbies".
"""
from __future__ import annotations

import re

from .models import User
from .traits import CAMPUSES, GROUPS, HUMOR_TYPES, INTEREST_KEYWORDS, INTERESTS, OTHER_COLLEGE, SCALE_DIMS

SCENARIOS = [
    {"id": "energy", "dim": "energy",
     "prompt": "It's Friday night and nothing is planned. What happens?",
     "options": [
         ("a", "Couch, takeaway, a show I've seen four times", 0.10),
         ("b", "Dinner with two or three close friends", 0.35),
         ("c", "I text around and end up wherever the night goes", 0.70),
         ("d", "I'm already out. The plan found me.", 0.92)]},
    {"id": "spontaneity", "dim": "spontaneity",
     "prompt": "You're planning a weekend trip. Which sounds like you?",
     "options": [
         ("a", "Itinerary, bookings, and a backup plan", 0.10),
         ("b", "A rough plan with a few fixed stops", 0.35),
         ("c", "Book the stay, figure out the rest when we get there", 0.65),
         ("d", "Pick a direction and drive", 0.90)]},
    {"id": "chronotype", "dim": "chronotype",
     "prompt": "When do you feel most alive?",
     "options": [
         ("a", "Sunrise", 0.10), ("b", "Mid-morning", 0.35),
         ("c", "Evening", 0.65), ("d", "Past midnight", 0.90)]},
    {"id": "openness", "dim": "openness",
     "prompt": "Something big happens to you, good or bad. What do you do?",
     "options": [
         ("a", "Sit with it first. I'll share when I'm ready.", 0.15),
         ("b", "Tell one person I trust", 0.40),
         ("c", "Tell a few people, with details", 0.70),
         ("d", "The group chat knows within minutes", 0.92)]},
    {"id": "conflict", "dim": "conflict",
     "prompt": "You and someone close disagree. What's your move?",
     "options": [
         ("a", "Take a few hours alone, then talk when I'm calm", 0.15),
         ("b", "Cool off, then talk it through the same day", 0.45),
         ("c", "Talk it out that evening", 0.70),
         ("d", "Right now. Let's sort it out.", 0.92)]},
    {"id": "reply_style", "dim": "reply_style",
     "prompt": "Texting someone you like. What's your rhythm?",
     "options": [
         ("a", "I reply when there's something worth saying", 0.15),
         ("b", "A few good exchanges a day", 0.40),
         ("c", "Steady back and forth through the day", 0.70),
         ("d", "A running commentary on my life", 0.92)]},
    {"id": "ambition", "dim": "ambition",
     "prompt": "Five years from now, what matters most?",
     "options": [
         ("a", "A calm, balanced life", 0.15),
         ("b", "A stable career with time for everything else", 0.40),
         ("c", "Real progress in something I care about", 0.70),
         ("d", "Building something big", 0.92)]},
    {"id": "family", "dim": "family",
     "prompt": "How close is family to your daily life?",
     "options": [
         ("a", "I like my independence. We catch up now and then.", 0.15),
         ("b", "Close, but with space", 0.40),
         ("c", "Weekly calls, big occasions together", 0.70),
         ("d", "Family is part of every big decision", 0.92)]},
    {"id": "tradition", "dim": "tradition",
     "prompt": "Picture a good life at thirty. How traditional is it?",
     "options": [
         ("a", "Defined by me, not by tradition", 0.10),
         ("b", "Mostly modern, with a few customs I love", 0.35),
         ("c", "Rooted in tradition with modern touches", 0.70),
         ("d", "Tradition guides the big things", 0.90)]},
    {"id": "money", "dim": "money",
     "prompt": "An unexpected ₹10,000 lands in your account. What happens?",
     "options": [
         ("a", "Straight into savings", 0.10),
         ("b", "Mostly saved, with a small treat", 0.35),
         ("c", "Half saved, half enjoyed", 0.60),
         ("d", "Spent on an experience I'll remember", 0.90)]},
]

HUMOR_OPTIONS = [
    ("dry", "Dry", "Deadpan and understated. The joke is in what you didn't say."),
    ("goofy", "Goofy", "Silly voices, terrible puns, zero shame."),
    ("sarcastic", "Sarcastic", "Quick comebacks and affectionate roasting."),
    ("wholesome", "Wholesome", "Warm, gentle, makes everyone feel included."),
    ("referential", "Reference-heavy", "Movie quotes, memes, and inside jokes only fans get."),
]

PRIORITY_OPTIONS = [
    ("vibe", "Their vibe and personality"),
    ("communication", "How we talk to each other"),
    ("values_interests", "Shared values and interests"),
    ("humor", "Sense of humor"),
]

CITIES = ["Bengaluru", "Mumbai", "Delhi", "Pune"]


def public_questionnaire() -> dict:
    return {
        "scenarios": [{"id": q["id"], "prompt": q["prompt"],
                       "options": [{"id": o[0], "text": o[1]} for o in q["options"]]} for q in SCENARIOS],
        "humor": [{"id": h[0], "label": h[1], "blurb": h[2]} for h in HUMOR_OPTIONS],
        "interests": INTERESTS,
        "priorities": [{"id": p[0], "label": p[1]} for p in PRIORITY_OPTIONS],
        "cities": CITIES,
        "campuses": [*CAMPUSES, OTHER_COLLEGE],
    }


def traits_from_answers(answers: dict[str, str]) -> dict[str, float]:
    traits = {d: 0.5 for d in SCALE_DIMS}
    for q in SCENARIOS:
        pick = answers.get(q["id"])
        for oid, _text, value in q["options"]:
            if oid == pick:
                traits[q["dim"]] = value
    return traits


def interests_from_text(text: str) -> list[str]:
    """Keyword fallback used when no language model is configured."""
    low = text.lower()
    found = []
    for tag, words in INTEREST_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(w), low) for w in words):
            found.append(tag)
    return found


def build_user(uid: str, basics: dict, answers: dict[str, str], humor: list[str], interests: list[str],
               priorities: list[str], about: str = "", extra_interests: list[str] | None = None,
               week: int = 1) -> User:
    chosen = [t for t in interests if t in INTERESTS]
    for t in extra_interests or []:
        if t in INTERESTS and t not in chosen:
            chosen.append(t)
    humor = [h for h in humor if h in HUMOR_TYPES][:2] or ["wholesome"]
    priorities = [p for p in priorities if p in GROUPS][:2]
    return User(
        id=uid, name=basics["name"].strip()[:40] or "You", gender=basics["gender"], seeking=basics["seeking"],
        age=basics["age"], age_min=basics["age_min"], age_max=basics["age_max"], city=basics["city"],
        open_distance=bool(basics.get("open_distance", False)), intent=basics["intent"],
        traits=traits_from_answers(answers), humor=humor, interests=chosen[:8], priorities=priorities,
        bio=about.strip()[:240], synthetic=False, joined_week=week,
        strict_intent=bool(basics.get("strict_intent", False)), private=bool(basics.get("private", False)),
        verified_only=bool(basics.get("verified_only", False)),
        campus=basics.get("campus", "") if basics.get("campus", "") in (*CAMPUSES, OTHER_COLLEGE) else "",
    )
