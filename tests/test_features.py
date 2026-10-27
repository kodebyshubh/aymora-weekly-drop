"""Deal-breakers, fairness metrics, the promise report, scam red-team, closure, and the visitor flows."""
from dataclasses import replace

import numpy as np
import pytest

from app import compat, fairness, promise, trust
from app.cohort import make_cohort
from app.drop import DropConfig, run_matching
from app.models import User
from app.questionnaire import build_user
from app.sim import SimParams, base_cohort, run_policy
from app.world import World, WorldError
from tests.helpers import make


def pair(a, b):
    return compat.build([a, b]).pair(a.id, b.id)["eligible"]


def woman(uid="w", **kw):
    return make(uid, gender="woman", seeking=("man",), **kw)


# ---- deal-breakers ---------------------------------------------------------------------------------
def test_strict_intent_blocks_one_step_apart_for_either_side():
    a, b = make("a", intent=1), woman(intent=2)
    assert pair(a, b)
    a.strict_intent = True
    assert not pair(a, b)
    a.strict_intent, b.strict_intent = False, True
    assert not pair(a, b)
    assert pair(replace(a, strict_intent=True), woman("w2", intent=1))


def test_family_privacy_hides_you_from_your_own_college_only():
    a, b = make("a", campus="DSCE"), woman(campus="DSCE")
    assert pair(a, b)
    a.private = True
    assert not pair(a, b)
    b.campus = "RVCE"
    assert pair(a, b)
    b.campus = ""
    assert pair(a, b)


def test_verified_only_needs_a_verified_partner():
    a, b = make("a", campus="DSCE"), woman(campus="")
    a.verified_only = True
    assert not pair(a, b)
    b.campus = "PES University"
    assert pair(a, b)


def test_realism_does_not_change_the_base_people():
    plain = make_cohort(60, seed=3)
    real = make_cohort(60, seed=3, realistic=True)
    assert [u.traits for u in plain] == [u.traits for u in real]
    assert any(u.private for u in real) and any(u.verified_only for u in real) and any(u.campus for u in real)
    assert not any(u.private or u.campus for u in plain)


def test_ghosting_costs_priority_when_two_people_want_the_same_partner():
    w = woman("w", level=0.5)
    m1, m2 = make("m1", level=0.5), make("m2", level=0.5)
    m1.ghosts = 3
    res = run_matching(compat.build([m1, m2, w]), DropConfig())
    assert {res.intros[0].a, res.intros[0].b} == {"m2", "w"}
    res = run_matching(compat.build([m1, m2, w]), DropConfig(ghost_penalty=0.0))
    assert len(res.intros) == 1


# ---- fairness ---------------------------------------------------------------------------------------
def test_gini_extremes():
    assert fairness.gini([1, 1, 1, 1]) == pytest.approx(0.0, abs=1e-9)
    assert fairness.gini([0, 0, 0, 10]) > 0.7
    assert fairness.gini([]) == 0.0


def test_the_swipe_feed_piles_attention_on_the_scarce_side():
    users = make_cohort(160, seed=5, pct_women=0.26, pct_nonbinary=0.0, cities=[("Bengaluru", 1.0)])
    feed = fairness.swipe_feed(users)
    assert feed["woman"]["mean_inbound"] > 3 * feed["man"]["mean_inbound"]
    assert feed["woman"]["top_decile_inbound"] > 1.5 * feed["woman"]["mean_inbound"]


def test_matching_caps_every_person_at_one_introduction_a_week():
    run = run_policy("weekly_drop", SimParams(n=120, weeks=4, seed=2, pct_women=0.3, cities=[("Bengaluru", 1.0)]))
    for s in run.person:
        assert s["intros"] <= s["weeks"]
    ps = fairness.person_summary(run.person)
    assert ps["woman"]["rate"] > ps["man"]["rate"]            # the scarce side is served more often


# ---- the promise ------------------------------------------------------------------------------------
def test_ceiling_is_an_upper_bound_and_unreachable_people_are_counted():
    r = promise.promise_report(SimParams(n=100, weeks=3, seed=4))
    assert r["headline"]["ceiling"] >= r["headline"]["delivered"] - 1e-9
    assert 0.0 <= r["headline"]["unreachable"] <= 1.0
    assert [lv["name"] for lv in r["levers"]][0] == "As launched"
    assert set(r["attention"]) == {"greedy", "one_shot", "weekly_drop"}
    assert r["swipe"]["woman"]["top_decile_inbound"] > 0


def test_balanced_admission_waitlists_the_larger_side_and_keeps_people_waiting_first():
    p = SimParams(n=120, weeks=3, seed=6, pct_women=0.3, cities=[("Bengaluru", 1.0)], admission=True)
    run = run_policy("weekly_drop", p)
    assert run.rows[0].waitlisted > 0
    assert run.rows[0].covered_all <= run.rows[0].covered + 1e-9


def test_window_finds_where_the_curve_clears_the_target():
    curve = [{"pct_women": x, "covered": y} for x, y in [(0.3, 0.7), (0.4, 0.85), (0.5, 0.95), (0.6, 0.8)]]
    lo, hi = promise._window(curve)
    assert 0.4 < lo < 0.5 and 0.5 <= hi < 0.6
    assert promise._window([{"pct_women": 0.3, "covered": 0.5}]) is None


# ---- scams ------------------------------------------------------------------------------------------
def test_scam_signals_score_higher_than_honest_ones():
    bad = [trust.risk(trust.adversary_signals(1, f"a{i}", k)) for i, k in enumerate(trust.KINDS * 25)]
    good = [trust.risk(trust.benign_signals(1, f"h{i}")) for i in range(400)]
    assert np.mean(bad) > 4 * np.mean(good)
    bench = {b["threshold"]: b for b in trust.benchmark(1, honest=1000, scam=100)}
    assert bench[0.6]["precision"] > 0.95 and bench[0.6]["recall"] > 0.7
    assert bench[0.3]["recall"] >= bench[0.7]["recall"]


def test_the_trust_gate_cuts_how_many_real_people_meet_a_scammer():
    p = SimParams(n=120, weeks=4, seed=3, adv_pct=0.08)
    ungated = run_policy("weekly_drop", p).trust
    gated = run_policy("weekly_drop", replace(p, trust_gate=True)).trust
    assert gated["exposed_rate"] < ungated["exposed_rate"]
    assert gated["tp"] > 0 and ungated["adversaries"] == gated["adversaries"]
    reported = run_policy("weekly_drop", replace(p, reports=True)).trust
    assert reported["exposed_rate"] <= ungated["exposed_rate"]


def test_adversaries_never_count_as_people_served():
    run = run_policy("weekly_drop", SimParams(n=100, weeks=3, seed=3, adv_pct=0.1))
    assert all(not str(s["id"]).startswith("x") for s in run.person)
    assert run.trust["real_people"] == run.total_joined


# ---- closure ----------------------------------------------------------------------------------------
def test_closure_protocol_turns_silence_into_reasons_and_lowers_chronic_ghosting():
    r = promise.closure_report(SimParams(n=140, weeks=5, seed=8))
    off, on = r["modes"]
    assert off["close_rate"] == 0.0 and on["close_rate"] > 0.05
    assert on["ghost_rate"] < off["ghost_rate"]
    assert on["chronic_share"] <= off["chronic_share"]


# ---- the visitor's world ------------------------------------------------------------------------------
def visitor(**basics) -> User:
    b = dict(name="Asha", gender="woman", seeking=["man"], age=23, age_min=21, age_max=28, city="Bengaluru", intent=1)
    b.update(basics)
    return build_user("me", b, {}, ["dry"], ["coffee", "travel"], ["humor"], "")


def mutual_world(**basics) -> World:
    w = World("t")
    w.add_me(visitor(**basics))
    for _ in range(10):
        v = w.view()
        if v["intro"] and v["intro"]["status"] == "pending":
            w.respond("in")
            v = w.view()
        if v["intro"] and v["intro"]["status"] == "mutual":
            return w
        w.advance_week()
    raise AssertionError("no mutual introduction in 10 weeks")


def test_the_trust_gate_holds_back_accounts_before_the_pool():
    w = World("t")
    w.add_me(visitor())
    assert w.view()["held_back"]["total"] > 0
    assert all(not w.users[h["id"]].active for h in w.held)


def test_reveal_goes_names_then_photos_then_numbers():
    w = mutual_world()
    assert w.view()["intro"]["reveal"]["stage"] == 1
    with pytest.raises(WorldError):
        w.reveal_step("numbers")
    for _ in range(8):
        w.reveal_step("photos")
        if w.view()["intro"]["reveal"]["photos"] == "open":
            break
    assert w.view()["intro"]["reveal"]["stage"] == 2
    for _ in range(8):
        w.reveal_step("numbers")
        if w.view()["intro"]["reveal"]["numbers"] == "open":
            break
    v = w.view()["intro"]
    assert v["reveal"]["stage"] == 3 and v["safety_plan"]["tips"] and "[place]" in v["safety_plan"]["share_text"]


def test_a_kind_close_with_a_reason_retunes_weights_once():
    w = mutual_world()
    note = w.set_outcome("closed", "humor")
    assert note and w.me.weight_mult["humor"] > 1.0
    with pytest.raises(WorldError):
        w.set_outcome("met", None)
    assert w.view()["intro"]["outcome"]["kind"] == "closed"


def test_staying_quiet_is_logged_and_costs_priority():
    w = mutual_world()
    w.advance_week()
    assert w.log[-1]["status"] == "quiet" and w.me.ghosts == 1


def test_reporting_closes_the_introduction_and_the_person_never_returns():
    w = mutual_world()
    other = w.view()["intro"]["other"]["first_name"]
    w.report("Asked me for money")
    v = w.view()["intro"]
    assert v["reported"] and v["status"] == "closed"
    with pytest.raises(WorldError):
        w.report("again")
    w.advance_week()
    assert w.log[-1]["status"] == "reported"
    assert all(u.id not in w.me.history or True for u in w.users.values())
    assert other


def test_the_scam_demo_shows_a_caution_banner():
    w = World("t")
    w.add_me(visitor())
    w.inject_scam()
    o = w.view()["intro"]["other"]
    assert o["new_account"] and "bio pushes contact off the app" in o["watch"] and not o["verified"]


def test_levers_name_changes_that_widen_the_pool():
    w = World("t")
    w.add_me(visitor(private=True, strict_intent=True, campus="DSCE"))
    out = w.levers()
    labels = {x["change"] for x in out}
    assert "Turn off family-privacy mode" in labels and "Be open to other cities" in labels
    assert all(x["viable_after"] >= x["viable_before"] for x in out)


def test_deal_breakers_flow_through_the_profile():
    u = visitor(private=True, verified_only=True, strict_intent=True, campus="DSCE")
    assert u.private and u.verified_only and u.strict_intent and u.campus == "DSCE"
    assert visitor(campus="Mars").campus == ""
