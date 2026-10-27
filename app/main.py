"""FastAPI app: the visitor's drop, the questionnaire, and the engine room simulator."""
from __future__ import annotations

import os
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from . import llm, promise
from .questionnaire import CITIES, build_user, interests_from_text, public_questionnaire
from .sim import POLICIES, POLICY_LABEL, SimParams, compare, frontier
from .traits import CAMPUSES, GENDERS, GROUPS, GROUP_LABEL, INTERESTS, OTHER_COLLEGE, SURVEY, SURVEY_PHYSICAL_APPEARANCE
from .world import World, WorldError, WorldStore

STATIC = Path(__file__).resolve().parent.parent / "static"

@asynccontextmanager
async def lifespan(_app):
    if os.environ.get("AYMORA_WARM", "1") == "1":
        threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="Aymora Weekly Drop", version="1.1", lifespan=lifespan)
store = WorldStore()


# ---- request models ------------------------------------------------------------------------------
class Basics(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    gender: str
    seeking: list[str] = Field(min_length=1)
    age: int = Field(ge=18, le=60)
    age_min: int = Field(ge=18, le=60)
    age_max: int = Field(ge=18, le=60)
    city: str
    open_distance: bool = False
    intent: int = Field(ge=0, le=2)
    strict_intent: bool = False
    private: bool = False
    verified_only: bool = False
    campus: str = ""

    @model_validator(mode="after")
    def _check(self):
        if self.campus and self.campus not in (*CAMPUSES, OTHER_COLLEGE):
            raise ValueError("unknown campus")
        if self.gender not in GENDERS or any(s not in GENDERS for s in self.seeking):
            raise ValueError("gender and seeking must be man, woman or nonbinary")
        if self.age_min > self.age_max:
            raise ValueError("age_min must not exceed age_max")
        if self.city not in CITIES:
            raise ValueError("unknown city")
        return self


class ProfileIn(BaseModel):
    basics: Basics
    answers: dict[str, str]
    humor: list[str] = Field(min_length=1, max_length=2)
    interests: list[str] = Field(default_factory=list, max_length=8)
    priorities: list[str] = Field(default_factory=list, max_length=2)
    about: str = Field(default="", max_length=400)


class RespondIn(BaseModel):
    action: str  # in | pass


class FeedbackIn(BaseModel):
    rating: str            # great | fine | no
    reason: str | None = None


class RevealIn(BaseModel):
    step: str              # photos | numbers


class OutcomeIn(BaseModel):
    kind: str              # talking | met | closed
    reason: str | None = None


class ReportIn(BaseModel):
    reason: str = Field(default="Something felt wrong", max_length=60)


class SimIn(BaseModel):
    n: int = Field(default=200, ge=60, le=400)
    weeks: int = Field(default=6, ge=2, le=10)
    pct_women: float = Field(default=0.45, ge=0.2, le=0.8)
    inflow_pct: float = Field(default=0.10, ge=0.0, le=0.3)
    floor: float = Field(default=0.62, ge=0.55, le=0.85)
    one_city: bool = False
    realistic: bool = False
    adv_pct: float = Field(default=0.05, ge=0.01, le=0.15)
    seed: int = Field(default=11, ge=0, le=9999)


# ---- helpers ------------------------------------------------------------------------------------
def _world(sid: str) -> World:
    w = store.get(sid)
    if w is None or w.me_id is None:
        raise HTTPException(404, "Session not found. Build your profile again.")
    return w


# ---- routes -------------------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm.enabled()}


@app.get("/api/questionnaire")
def questionnaire():
    q = public_questionnaire()
    q["survey"] = {"weights": SURVEY, "physical_appearance": SURVEY_PHYSICAL_APPEARANCE,
                   "labels": GROUP_LABEL}
    return q


@app.post("/api/profile")
def create_profile(body: ProfileIn):
    sid = uuid.uuid4().hex[:12]
    extra = None
    if body.about.strip():
        extra = llm.extract_interests(body.about, INTERESTS) if llm.enabled() else None
        if extra is None:
            extra = interests_from_text(body.about)
    user = build_user(sid, body.basics.model_dump(), body.answers, body.humor, body.interests,
                      body.priorities, body.about, extra)
    world = store.create(sid)
    world.add_me(user)
    return {"sid": sid, "added_interests": [t for t in (extra or []) if t not in body.interests]}


@app.get("/api/drop/{sid}")
def get_drop(sid: str):
    return _world(sid).view()


@app.post("/api/drop/{sid}/respond")
def respond(sid: str, body: RespondIn):
    w = _world(sid)
    try:
        w.respond(body.action)
    except WorldError as e:
        raise HTTPException(400, str(e))
    return w.view()


@app.post("/api/drop/{sid}/feedback")
def feedback(sid: str, body: FeedbackIn):
    w = _world(sid)
    try:
        note = w.feedback(body.rating, body.reason if body.reason in GROUPS else None)
    except WorldError as e:
        raise HTTPException(400, str(e))
    v = w.view()
    v["note"] = note
    return v


@app.post("/api/drop/{sid}/reveal")
def reveal(sid: str, body: RevealIn):
    w = _world(sid)
    try:
        w.reveal_step(body.step)
    except WorldError as e:
        raise HTTPException(400, str(e))
    return w.view()


@app.post("/api/drop/{sid}/outcome")
def outcome(sid: str, body: OutcomeIn):
    w = _world(sid)
    try:
        note = w.set_outcome(body.kind, body.reason)
    except WorldError as e:
        raise HTTPException(400, str(e))
    v = w.view()
    v["note"] = note
    return v


@app.post("/api/drop/{sid}/report")
def report(sid: str, body: ReportIn):
    w = _world(sid)
    try:
        w.report(body.reason)
    except WorldError as e:
        raise HTTPException(400, str(e))
    return w.view()


@app.get("/api/drop/{sid}/levers")
def levers(sid: str):
    return {"levers": _world(sid).levers()}


@app.post("/api/drop/{sid}/demo-scam")
def demo_scam(sid: str):
    w = _world(sid)
    w.inject_scam()
    return w.view()


@app.post("/api/drop/{sid}/next-week")
def next_week(sid: str):
    w = _world(sid)
    if w.week >= 12:
        raise HTTPException(400, "This demo stops at week 12.")
    w.advance_week()
    return w.view()


def _cities(one_city: bool):
    return [("Bengaluru", 1.0)] if one_city else None


@lru_cache(maxsize=64)
def _sim_cached(key: tuple) -> dict:
    n, weeks, pct_women, inflow, floor, one_city, seed, realistic = key
    params = SimParams(n=n, weeks=weeks, pct_women=pct_women, pct_nonbinary=0.02, inflow_pct=inflow,
                       floor=floor, seed=seed, cities=_cities(one_city), realistic=realistic)
    runs = compare(params)
    out = {"params": {"n": n, "weeks": weeks, "pct_women": pct_women, "inflow_pct": inflow, "floor": floor,
                      "one_city": one_city, "realistic": realistic, "seed": seed},
           "labels": POLICY_LABEL, "policies": {}}
    for name in POLICIES:
        r = runs[name]
        out["policies"][name] = {
            "rows": [asdict(x) for x in r.rows],
            "retention": r.retention,
            "final_active": r.final_active,
            "total_joined": r.total_joined,
            "unmatched_reasons": r.unmatched_reasons,
            "supply": r.supply,
            "avg_score": (sum(r.all_scores) / len(r.all_scores)) if r.all_scores else 0.0,
        }
    return out


@app.post("/api/sim")
def simulate(body: SimIn):
    key = (body.n, body.weeks, round(body.pct_women, 3), round(body.inflow_pct, 3),
           round(body.floor, 3), body.one_city, body.seed, body.realistic)
    return _sim_cached(key)


@lru_cache(maxsize=32)
def _frontier_cached(key: tuple) -> list[dict]:
    n, weeks, pct_women, inflow, one_city, seed = key
    params = SimParams(n=n, weeks=weeks, pct_women=pct_women, pct_nonbinary=0.02, inflow_pct=inflow,
                       seed=seed, cities=_cities(one_city))
    return frontier(params, [0.55, 0.60, 0.64, 0.68, 0.72, 0.76])


@app.post("/api/frontier")
def get_frontier(body: SimIn):
    key = (min(body.n, 240), min(body.weeks, 5), round(body.pct_women, 3), round(body.inflow_pct, 3),
           body.one_city, body.seed)
    return {"points": _frontier_cached(key)}


def _params(body: SimIn, **over) -> SimParams:
    return SimParams(n=body.n, weeks=body.weeks, pct_women=round(body.pct_women, 3), pct_nonbinary=0.02,
                     inflow_pct=round(body.inflow_pct, 3), floor=round(body.floor, 3), seed=body.seed,
                     cities=_cities(body.one_city), realistic=body.realistic, **over)


def _key(body: SimIn) -> tuple:
    return (body.n, body.weeks, round(body.pct_women, 3), round(body.inflow_pct, 3), round(body.floor, 3),
            body.one_city, body.realistic, body.seed, round(body.adv_pct, 3))


@lru_cache(maxsize=24)
def _promise_cached(key: tuple) -> dict:
    n, weeks, pw, inflow, floor, one_city, realistic, seed, _ = key
    return promise.promise_report(SimParams(n=n, weeks=weeks, pct_women=pw, pct_nonbinary=0.02, inflow_pct=inflow,
                                            floor=floor, seed=seed, cities=_cities(one_city), realistic=realistic))


@lru_cache(maxsize=24)
def _curve_cached(key: tuple) -> dict:
    n, weeks, pw, inflow, floor, one_city, realistic, seed, _ = key
    return promise.curve_report(SimParams(n=n, weeks=weeks, pct_women=pw, pct_nonbinary=0.02, inflow_pct=inflow,
                                          floor=floor, seed=seed, cities=_cities(one_city), realistic=realistic))


@lru_cache(maxsize=24)
def _redteam_cached(key: tuple) -> dict:
    n, weeks, pw, inflow, floor, one_city, realistic, seed, adv = key
    return promise.redteam_report(SimParams(n=n, weeks=weeks, pct_women=pw, pct_nonbinary=0.02, inflow_pct=inflow,
                                            floor=floor, seed=seed, cities=_cities(one_city)), adv)


@lru_cache(maxsize=24)
def _closure_cached(key: tuple) -> dict:
    n, weeks, pw, inflow, floor, one_city, realistic, seed, _ = key
    return promise.closure_report(SimParams(n=n, weeks=weeks, pct_women=pw, pct_nonbinary=0.02, inflow_pct=inflow,
                                            floor=floor, seed=seed, cities=_cities(one_city)))


@app.post("/api/promise")
def api_promise(body: SimIn):
    return _promise_cached(_key(body))


@app.post("/api/promise/curve")
def api_curve(body: SimIn):
    return _curve_cached(_key(body))


@app.post("/api/redteam")
def api_redteam(body: SimIn):
    return _redteam_cached(_key(body))


@app.post("/api/closure")
def api_closure(body: SimIn):
    return _closure_cached(_key(body))


def _warm() -> None:
    """Precompute the default engine-room views so the first visitor does not wait."""
    body = SimIn()
    for fn in (simulate, api_promise, api_redteam, api_closure, api_curve, get_frontier):
        try:
            fn(body)
        except Exception:  # warm-up is best effort
            pass


# ---- static -------------------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
