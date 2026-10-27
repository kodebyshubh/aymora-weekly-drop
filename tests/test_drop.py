from dataclasses import replace

import numpy as np

from app import compat
from app.cohort import make_cohort
from app.drop import DropConfig, run_greedy, run_matching, supply_gaps, tier_for
from tests.helpers import make


def test_everyone_gets_at_most_one_introduction():
    users = make_cohort(200, seed=2)
    m = compat.build(users)
    res = run_matching(m, DropConfig())
    seen = []
    for it in res.intros:
        seen += [it.a, it.b]
    assert len(seen) == len(set(seen))
    assert len(res.intros) * 2 + len(res.unmatched) == res.pool


def test_every_introduction_respects_hard_filters_and_the_floor():
    users = make_cohort(200, seed=4)
    m = compat.build(users)
    cfg = DropConfig(floor=0.62)
    res = run_matching(m, cfg)
    assert res.intros
    for it in res.intros:
        p = m.pair(it.a, it.b)
        assert p["eligible"]
        assert p["mutual"] >= cfg.floor - 1e-9      # nobody has waited, so the floor is the full floor
        assert it.tier == tier_for(it.score)


def test_pool_wide_matching_beats_first_come_first_served():
    wins = 0
    for seed in (1, 2, 3, 4, 5):
        users = make_cohort(180, seed=seed)
        m = compat.build(users)
        cfg = DropConfig()
        order = list(range(len(users)))
        np.random.default_rng(seed).shuffle(order)
        best = len(run_matching(m, cfg).intros)
        greedy = len(run_greedy(m, cfg, order).intros)
        assert best >= greedy
        wins += best > greedy
    assert wins >= 3


def _pair_with_score():
    a = make("a", level=0.5, spontaneity=0.5, humor=("dry",), interests=("coffee",))
    b = make("b", gender="woman", seeking=("man",), level=0.5, spontaneity=0.5, humor=("sarcastic",),
             interests=("music",), conflict=0.8, family=0.7)
    s = compat.build([a, b]).pair("a", "b")["mutual"]
    return a, b, s


def test_waiting_relaxes_the_floor_for_the_person_who_waited():
    a, b, s = _pair_with_score()
    cfg = DropConfig(floor=s + 0.02, min_floor=0.0, relax_per_wait=0.03)
    assert run_matching(compat.build([a, b]), cfg).intros == []          # fresh: just below the floor
    a.wait = 1
    assert len(run_matching(compat.build([a, b]), cfg).intros) == 1      # waited a week: now clears it


def test_carryover_off_means_no_relaxation():
    a, b, s = _pair_with_score()
    a.wait = 5
    cfg = DropConfig(floor=s + 0.02, min_floor=0.0, carryover=False)
    assert run_matching(compat.build([a, b]), cfg).intros == []


def test_the_quality_guardrail_never_relaxes():
    a, b, s = _pair_with_score()
    a.wait = 50
    cfg = DropConfig(floor=0.9, min_floor=s + 0.05, relax_per_wait=0.5)
    assert run_matching(compat.build([a, b]), cfg).intros == []


def test_waiting_gives_priority_when_two_people_want_the_same_partner():
    # one woman, two men who both clear the floor; the man who waited gets the introduction
    w = make("w", gender="woman", seeking=("man",), level=0.5)
    m1 = make("m1", level=0.5)
    m2 = make("m2", level=0.5)
    m1.wait = 3
    res = run_matching(compat.build([m1, m2, w]), DropConfig())
    assert len(res.intros) == 1
    assert {res.intros[0].a, res.intros[0].b} == {"m1", "w"}
    flipped = replace(DropConfig(), carryover=False)
    m1.wait = 0
    m2.wait = 3
    res2 = run_matching(compat.build([m1, m2, w]), DropConfig())
    assert {res2.intros[0].a, res2.intros[0].b} == {"m2", "w"}
    assert len(run_matching(compat.build([m1, m2, w]), flipped).intros) == 1


def test_unmatched_reasons_are_labelled():
    lone = make("lone", city="Pune")                              # nobody in Pune
    a = make("a", level=0.1, humor=("dry",), interests=("anime",))
    b = make("b", gender="woman", seeking=("man",), level=0.95, humor=("wholesome",), interests=("pets",))
    res = run_matching(compat.build([lone, a, b]), DropConfig(floor=0.7))
    reasons = {u.id: u.reason for u in res.unmatched}
    assert reasons["lone"] == "no_eligible"
    assert reasons["a"] == "below_floor" and reasons["b"] == "below_floor"


def test_outcompeted_when_good_partners_are_taken():
    w1 = make("w1", gender="woman", seeking=("man",), level=0.5)
    m1, m2 = make("m1", level=0.5), make("m2", level=0.5)
    m1.wait = 4
    res = run_matching(compat.build([m1, m2, w1]), DropConfig())
    un = {u.id: u.reason for u in res.unmatched}
    assert un == {"m2": "outcompeted"}


def test_supply_gaps_name_the_missing_kind_of_person():
    users = [make(f"m{i}") for i in range(6)] + [make("w0", gender="woman", seeking=("man",))]
    m = compat.build(users)
    res = run_matching(m, DropConfig())
    gaps = supply_gaps(m, res.unmatched)
    assert gaps and gaps[0]["seeking"] == ["woman"] and gaps[0]["city"] == "Bengaluru"
    assert gaps[0]["people"] == 5 and gaps[0]["age_range"] == [20, 30]


def test_top_k_pruning_keeps_matching_valid():
    users = make_cohort(150, seed=9)
    m = compat.build(users)
    tight = run_matching(m, DropConfig(top_k=3))
    wide = run_matching(m, DropConfig(top_k=60))
    assert len(wide.intros) >= len(tight.intros) * 0.8
    for it in tight.intros:
        assert m.pair(it.a, it.b)["eligible"]


def test_tiers():
    assert tier_for(0.9) == "Strong" and tier_for(0.7) == "Good" and tier_for(0.6) == "Worth a hello"
