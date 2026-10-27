"""One visitor's sandbox: a synthetic pool of people plus the visitor, run week by week.

Each visitor gets their own World so nobody's demo changes under them. Everyone else in the pool is
synthetic. Their replies to the visitor are drawn from the same yes-probability model the simulator uses.
"""
from __future__ import annotations

from dataclasses import replace

from . import compat, llm, trust
from .cohort import make_cohort
from .drop import DropConfig, DropResult, run_matching
from .explain import explain_pair
from .learn import apply_feedback
from .models import Intro, User
from .sim import p_yes, rand01
from .traits import GROUP_LABEL, GROUPS, OTHER_COLLEGE

EXTRA_REASONS = {"intent", "distance", "other"}

POOL_SIZE = 240
WEEKLY_INFLOW = 14


class WorldError(Exception):
    pass


def _fkey(it: Intro) -> tuple:
    return (it.week, it.a, it.b)


def _first(name: str) -> str:
    return name.split()[0]


class World:
    def __init__(self, sid: str, seed: int = 7, n: int = POOL_SIZE):
        self.sid = sid
        self.seed = seed
        self.week = 1
        self.cfg = DropConfig()
        self.users: dict[str, User] = {}
        self.held: list[dict] = []          # accounts held back by the trust gate, with the reasons
        self.reveal: dict[tuple, dict] = {}
        self.outcome: dict[tuple, dict] = {}
        self.reports: list[dict] = []
        self._screen(make_cohort(n, seed=seed, pct_women=0.47, pct_nonbinary=0.02, realistic=True)
                     + trust.make_adversaries(int(round(n * 0.04)), seed, 0, "x"), 0)
        self.me_id: str | None = None
        self.drop: DropResult = DropResult()
        self.intro_of: dict[str, Intro] = {}
        self.log: list[dict] = []
        self.notes: list[str] = []
        self._mats = None
        self._idf: dict[str, float] = {}
        self._feedback_given: set[tuple] = set()

    # ---- lifecycle ---------------------------------------------------------------------------
    def _screen(self, batch: list[User], week: int) -> None:
        """Trust gate: risky accounts are held back before they can enter any drop."""
        trust.attach_signals(batch, self.seed)
        for u in batch:
            if u.signals and trust.risk(u.signals) >= trust.QUARANTINE_AT:
                u.active = False
                self.held.append({"week": week, "id": u.id, "reasons": trust.reasons(u.signals)})
            self.users[u.id] = u

    @property
    def me(self) -> User:
        if not self.me_id:
            raise WorldError("Create a profile first.")
        return self.users[self.me_id]

    def add_me(self, user: User) -> None:
        user.joined_week = self.week
        self.users[user.id] = user
        self.me_id = user.id
        self.run_drop()

    def run_drop(self) -> None:
        live = [u for u in self.users.values() if u.active]
        self._mats = compat.build(live)
        self._idf = compat.interest_idf(live)
        self.drop = run_matching(self._mats, self.cfg, self.week)
        self.intro_of = {}
        for it in self.drop.intros:
            self.intro_of[it.a] = it
            self.intro_of[it.b] = it

    def advance_week(self) -> None:
        me_intro = self.intro_of.get(self.me_id) if self.me_id else None
        if self.me_id:
            if me_intro is None:
                un = next((x for x in self.drop.unmatched if x.id == self.me_id), None)
                self.log.append({"week": self.week, "status": "none", "reason": un.reason if un else None})
            else:
                other = self.users[me_intro.other(self.me_id)]
                status = me_intro.status if me_intro.status != "pending" else "expired"
                oc = self.outcome.get(_fkey(me_intro))
                if any(r["key"] == _fkey(me_intro) for r in self.reports):
                    status = "reported"
                elif me_intro.status == "mutual":
                    if oc is None:
                        status = "quiet"
                        self.me.ghosts += 1
                    else:
                        status = oc["kind"]
                self.log.append({"week": self.week, "status": status, "name": _first(other.name),
                                 "tier": me_intro.tier})
        for it in self.drop.intros:
            a, b = self.users[it.a], self.users[it.b]
            a.history.add(b.id)
            b.history.add(a.id)
            a.wait = b.wait = 0
        for un in self.drop.unmatched:
            self.users[un.id].wait += 1
        self.week += 1
        fresh = make_cohort(WEEKLY_INFLOW, seed=self.seed * 100 + self.week, pct_women=0.47, pct_nonbinary=0.02,
                            week=self.week, prefix=f"n{self.week}-", realistic=True)
        fresh += trust.make_adversaries(1, self.seed, self.week, "x")
        self._screen(fresh, self.week)
        self.run_drop()

    # ---- the visitor's actions -----------------------------------------------------------------
    def respond(self, action: str) -> None:
        it = self.intro_of.get(self.me_id or "")
        if it is None:
            raise WorldError("There is no introduction to answer this week.")
        if it.status != "pending":
            raise WorldError("This introduction is already settled.")
        me_is_a = it.a == self.me_id
        if action == "pass":
            if me_is_a:
                it.state_a = "pass"
            else:
                it.state_b = "pass"
            return
        if action != "in":
            raise WorldError("Unknown action.")
        other_id = it.other(self.me_id)
        their_fit = it.b_to_a if me_is_a else it.a_to_b
        yes = rand01(self.seed, "yes", self.week, other_id, self.me_id) < p_yes(their_fit)
        if me_is_a:
            it.state_a, it.state_b = "in", ("in" if yes else "pass")
        else:
            it.state_b, it.state_a = "in", ("in" if yes else "pass")

    def feedback(self, rating: str, reason: str | None) -> str | None:
        it = self.intro_of.get(self.me_id or "")
        if it is None:
            raise WorldError("There is no introduction to rate.")
        if _fkey(it) in self._feedback_given:
            raise WorldError("You already rated this introduction.")
        if rating not in ("great", "fine", "no"):
            raise WorldError("Unknown rating.")
        pair = self._mats.pair(it.a, it.b)
        note = apply_feedback(self.me, pair["groups"], rating, reason)
        self._feedback_given.add(_fkey(it))
        if note:
            self.notes.append(note)
        return note

    def _intro(self) -> Intro:
        it = self.intro_of.get(self.me_id or "")
        if it is None:
            raise WorldError("There is no introduction this week.")
        return it

    def reveal_step(self, step: str) -> None:
        """Photos, then numbers. Each needs both people to agree; the other side is a synthetic person."""
        it = self._intro()
        if it.status != "mutual":
            raise WorldError("Photos and numbers unlock only after a mutual yes.")
        if step not in ("photos", "numbers"):
            raise WorldError("Unknown step.")
        r = self.reveal.setdefault(_fkey(it), {k: {"you": False, "them": False, "tries": 0} for k in ("photos", "numbers")})
        if step == "numbers" and not (r["photos"]["you"] and r["photos"]["them"]):
            raise WorldError("Share photos first.")
        s = r[step]
        if s["you"] and s["them"]:
            raise WorldError("Already shared.")
        s["you"] = True
        s["tries"] += 1
        p = 0.9 if step == "photos" else 0.8
        s["them"] = rand01(self.seed, "reveal", step, self.week, it.other(self.me_id), s["tries"]) < p

    def set_outcome(self, kind: str, reason: str | None) -> str | None:
        """Closure protocol: tell us where it stands. A kind close with a reason retunes your weights."""
        it = self._intro()
        if it.status != "mutual":
            raise WorldError("There is nothing to close yet.")
        if kind not in ("talking", "met", "closed"):
            raise WorldError("Unknown outcome.")
        if reason is not None and reason not in GROUPS and reason not in EXTRA_REASONS:
            raise WorldError("Unknown reason.")
        key = _fkey(it)
        prev = self.outcome.get(key)
        if prev and prev["kind"] in ("met", "closed"):
            raise WorldError("This introduction is already closed.")
        self.outcome[key] = {"kind": kind, "reason": reason}
        note = None
        if kind in ("met", "closed") and key not in self._feedback_given:
            pair = self._mats.pair(it.a, it.b)
            if kind == "met":
                note = apply_feedback(self.me, pair["groups"], "great", None)
            elif reason in GROUPS:
                note = apply_feedback(self.me, pair["groups"], "no", reason)
            self._feedback_given.add(key)
            if note:
                self.notes.append(note)
        return note

    def report(self, reason: str) -> None:
        it = self._intro()
        other = self.users[it.other(self.me_id)]
        key = _fkey(it)
        if any(r["key"] == key for r in self.reports):
            raise WorldError("You already reported this account.")
        self.reports.append({"key": key, "id": other.id, "reason": reason[:60], "week": self.week})
        if it.a == self.me_id:
            it.state_a = "pass"
        else:
            it.state_b = "pass"
        self.me.history.add(other.id)
        self._feedback_given.add(key)

    def levers(self) -> list[dict]:
        """What would widen your options. Each change is tried on its own against the current pool."""
        me = self.me
        live = [u for u in self.users.values() if u.active]
        floor = self.cfg.floor

        def counts(user: User) -> tuple[int, int]:
            pool = [u for u in live if u.id != user.id] + [user]
            m = compat.build(pool)
            i = m.index[user.id]
            return int(m.eligible[i].sum()), int((m.eligible[i] & (m.mutual[i] >= floor)).sum())

        base = counts(me)
        tries: list[tuple[str, dict]] = [
            ("Widen your age range by 2 years on each end", {"age_min": max(18, me.age_min - 2), "age_max": min(60, me.age_max + 2)}),
        ]
        if not me.open_distance:
            tries.append(("Be open to other cities", {"open_distance": True}))
        if me.strict_intent:
            tries.append(("Allow people one step apart on what they are looking for", {"strict_intent": False}))
        if me.verified_only:
            tries.append(("Include people who have not verified a campus email", {"verified_only": False}))
        if me.private:
            tries.append(("Turn off family-privacy mode", {"private": False}))
        out = []
        for label, change in tries:
            alt = replace(me, **change)
            e, v = counts(alt)
            out.append({"change": label, "eligible_before": base[0], "eligible_after": e,
                        "viable_before": base[1], "viable_after": v})
        out.sort(key=lambda r: -(r["viable_after"] - r["viable_before"]))
        return out

    def inject_scam(self) -> None:
        """Demo control: a scam account that slips past the trust gate becomes this week's introduction."""
        me = self.me
        uid = f"x-demo-{self.week}"
        adv = replace(me, id=uid, name="Riya K.", gender=("woman" if "woman" in me.seeking else "man"),
                      seeking=[me.gender], age=max(me.age_min, min(me.age_max, me.age)), age_min=18, age_max=60,
                      synthetic=True, history=set(), weight_mult={}, priorities=list(me.priorities),
                      bio="New here! Message me on WhatsApp, I have an investment idea you will love.",
                      adversary="romance_scammer", wait=0, ghosts=0, private=False, strict_intent=False,
                      verified_only=False, campus=OTHER_COLLEGE if me.verified_only else "",
                      signals={"account_age_days": 3, "bio_dupe": 0, "offplatform_bio": 1, "money_words": 0,
                               "email_mismatch": 1, "prior_reports": 0, "photo_reuse": 0})
        adv.interests = list(me.interests)[:4]
        adv.humor = list(me.humor)
        self.users[uid] = adv
        live = [u for u in self.users.values() if u.active]
        self._mats = compat.build(live)
        self._idf = compat.interest_idf(live)
        old = self.intro_of.pop(me.id, None)
        if old is not None:
            self.drop.intros = [x for x in self.drop.intros if x is not old]
            self.intro_of.pop(old.other(me.id), None)
        pair = self._mats.pair(me.id, uid)
        it = Intro(a=me.id, b=uid, score=max(0.8, pair["mutual"]), a_to_b=max(0.8, pair["a_to_b"]),
                   b_to_a=max(0.8, pair["b_to_a"]), tier="Strong", week=self.week)
        self.drop.intros.append(it)
        self.intro_of[me.id] = it
        self.intro_of[uid] = it
        self.drop.unmatched = [x for x in self.drop.unmatched if x.id != me.id]

    def _held_view(self) -> dict:
        recent = [h for h in self.held if h["week"] == self.week]
        counts: dict[str, int] = {}
        for h in recent:
            for r in h["reasons"]:
                counts[r] = counts.get(r, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
        return {"this_week": len(recent), "total": len(self.held), "top_reasons": [r for r, _ in top]}

    def _plan(self, other: User) -> dict:
        name = _first(other.name)
        return {
            "tips": ["Pick a busy cafe or bookshop and meet before 6 pm for the first time.",
                     "Tell a friend where you will be and when. Share your live location for the first hour.",
                     "Travel on your own and pay for your own order.",
                     "Nobody real will ask you for money, a loan or an investment. If they do, stop and report."],
            "share_text": f"I'm meeting {name} for a coffee at [place] at [time]. I'll message you when I'm home.",
        }

    # ---- what the visitor sees -------------------------------------------------------------------
    def view(self) -> dict:
        me = self.me
        pool = sum(1 for u in self.users.values() if u.active)
        out: dict = {
            "week": self.week,
            "pool": pool,
            "week_stats": {"pool": self.drop.pool, "intros": len(self.drop.intros),
                           "covered": round(2 * len(self.drop.intros) / max(1, self.drop.pool), 3)},
            "log": self.log,
            "notes": self.notes,
            "waited": me.wait,
            "ghosts": me.ghosts,
            "held_back": self._held_view(),
            "profile": {"strict_intent": me.strict_intent, "private": me.private, "verified_only": me.verified_only,
                        "campus": me.campus, "open_distance": me.open_distance},
            "weights": {g: round(float(w), 3) for g, w in zip(GROUPS, self._mats.weights[self._mats.index[me.id]])},
            "intro": None,
            "unmatched": None,
        }
        it = self.intro_of.get(me.id)
        if it is not None:
            other = self.users[it.other(me.id)]
            ex = explain_pair(me, other, self._mats, self._idf)
            if llm.enabled():
                warmer = llm.reword(ex["reasons"])
                if warmer:
                    ex["reasons"] = warmer
            me_is_a = it.a == me.id
            mine, theirs = (it.state_a, it.state_b) if me_is_a else (it.state_b, it.state_a)
            revealed = it.status == "mutual"
            key = _fkey(it)
            rv = self.reveal.get(key)
            stage = 1
            if rv and rv["photos"]["you"] and rv["photos"]["them"]:
                stage = 2
                if rv["numbers"]["you"] and rv["numbers"]["them"]:
                    stage = 3
            risk_now = trust.risk(other.signals) if other.signals else 0.0
            watch = trust.reasons(other.signals) if trust.WATCH_AT <= risk_now < trust.QUARANTINE_AT else []
            reported = any(r["key"] == key for r in self.reports)
            out["intro"] = {
                "tier": it.tier,
                "score": round(it.score, 3),
                "your_fit": round(it.a_to_b if me_is_a else it.b_to_a, 3),
                "their_fit": round(it.b_to_a if me_is_a else it.a_to_b, 3),
                "status": it.status,
                "you": mine,
                "them": theirs,
                "feedback_given": key in self._feedback_given,
                "outcome": self.outcome.get(key),
                "reported": reported,
                "reveal": {"stage": stage if revealed else 0,
                           "photos": _ask(rv, "photos"), "numbers": _ask(rv, "numbers")},
                "safety_plan": self._plan(other) if (revealed and stage == 3) else None,
                "other": {
                    "first_name": _first(other.name),
                    "full_name": other.name if revealed else None,
                    "age": other.age,
                    "city": other.city,
                    "humor": other.humor[0],
                    "verified": bool(other.campus),
                    "campus": other.campus if revealed else None,
                    "watch": watch,
                    "new_account": bool(other.signals) and other.signals.get("account_age_days", 365) < 7,
                    "interests": other.interests[:5],
                    "bio": other.bio if revealed else None,
                },
                "explain": ex,
            }
        else:
            un = next((x for x in self.drop.unmatched if x.id == me.id), None)
            if un is not None:
                out["unmatched"] = {"reason": un.reason, "eligible": un.eligible, "viable": un.viable,
                                    "text": _unmatched_text(un, self.cfg)}
        return out


def _ask(rv: dict | None, step: str) -> str:
    if not rv:
        return "idle"
    s = rv[step]
    if s["you"] and s["them"]:
        return "open"
    if s["you"]:
        return "declined"
    return "idle"


def _unmatched_text(un, cfg: DropConfig) -> str:
    if un.reason == "no_eligible":
        return ("No one in the pool fits your hard preferences right now (gender, age range, city or intent). "
                "That is a supply gap on our side, not something you did.")
    if un.reason == "below_floor":
        return (f"{un.eligible} people fit your preferences, but none cleared our quality floor. "
                "We would rather skip a week than send a weak introduction. "
                "Your floor relaxes a little next week and you move up the line.")
    return (f"{un.viable} good fits exist, but each is a stronger fit for someone else this week. "
            "You are first in line next week.")


class WorldStore:
    """In-memory sessions, oldest evicted first."""

    def __init__(self, cap: int = 200):
        self.cap = cap
        self._w: dict[str, World] = {}

    def create(self, sid: str) -> World:
        if len(self._w) >= self.cap:
            self._w.pop(next(iter(self._w)))
        w = World(sid)
        self._w[sid] = w
        return w

    def get(self, sid: str) -> World | None:
        return self._w.get(sid)
