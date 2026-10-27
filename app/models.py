"""Plain dataclasses used by the engine (kept free of web concerns so they are easy to test)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    name: str
    gender: str                      # man | woman | nonbinary
    seeking: list[str]               # genders this person wants to meet
    age: int
    age_min: int
    age_max: int
    city: str
    open_distance: bool
    intent: int                      # 0 casual, 1 open to long term, 2 serious
    traits: dict[str, float]         # SCALE_DIMS -> 0..1
    humor: list[str]                 # [primary] or [primary, secondary]
    interests: list[str]
    priorities: list[str] = field(default_factory=list)   # groups this person cares about most
    weight_mult: dict[str, float] = field(default_factory=dict)  # learned from feedback
    bio: str = ""
    synthetic: bool = False
    wait: int = 0                    # consecutive weeks without an introduction
    history: set[str] = field(default_factory=set)  # ids already introduced (never repeat)
    active: bool = True
    joined_week: int = 0
    strict_intent: bool = False      # only meet people with exactly the same intent
    private: bool = False            # family-privacy mode: never shown to people from my own college circle
    campus: str = ""                 # campus-verified college ("" = unverified; verification is mocked here)
    verified_only: bool = False      # only meet campus-verified people
    ghosts: int = 0                  # introductions where they went quiet without closing
    ghost_prob: float = 0.0          # simulator only: how likely this synthetic person is to go quiet
    adversary: str | None = None     # simulator only: ground truth for scam red-team runs
    signals: dict = field(default_factory=dict)  # behavioural signals the trust model can see


@dataclass
class Intro:
    a: str                           # user id
    b: str                           # user id
    score: float                     # mutual compatibility, 0..1
    a_to_b: float
    b_to_a: float
    tier: str
    week: int = 0
    state_a: str = "pending"         # pending | in | pass
    state_b: str = "pending"

    @property
    def status(self) -> str:
        if self.state_a == "in" and self.state_b == "in":
            return "mutual"
        if "pass" in (self.state_a, self.state_b):
            return "closed"
        return "pending"

    def other(self, uid: str) -> str:
        return self.b if uid == self.a else self.a
