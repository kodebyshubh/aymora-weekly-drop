import numpy as np

from app import llm
from app.learn import MULT_MAX, MULT_MIN, apply_feedback
from app.questionnaire import SCENARIOS, build_user, interests_from_text, traits_from_answers
from app.sim import SimParams, compare, frontier, p_yes, rand01, run_policy
from app.traits import GROUPS, INTERESTS, SCALE_DIMS
from tests.helpers import make


# ---- simulator -----------------------------------------------------------------------------------
def test_simulation_is_deterministic():
    p = SimParams(n=100, weeks=3, seed=5)
    a = run_policy("weekly_drop", p)
    b = run_policy("weekly_drop", p)
    assert [r.covered for r in a.rows] == [r.covered for r in b.rows]
    assert a.retention == b.retention


def test_weekly_drop_is_at_least_as_good_as_the_baselines():
    cov = {k: [] for k in ("greedy", "one_shot", "weekly_drop")}
    ret = {k: [] for k in cov}
    wait = {k: [] for k in cov}
    for seed in (11, 12, 13):
        runs = compare(SimParams(n=140, weeks=5, seed=seed))
        for k, r in runs.items():
            cov[k].append(np.mean([x.covered for x in r.rows]))
            ret[k].append(r.retention)
            wait[k].append(np.mean([x.waited_2plus for x in r.rows]))
    assert np.mean(cov["weekly_drop"]) > np.mean(cov["greedy"])
    assert np.mean(cov["weekly_drop"]) >= np.mean(cov["one_shot"]) - 0.005
    assert np.mean(ret["weekly_drop"]) > np.mean(ret["greedy"])
    assert np.mean(wait["weekly_drop"]) < np.mean(wait["one_shot"])


def test_week_rows_are_consistent():
    run = run_policy("weekly_drop", SimParams(n=100, weeks=4, seed=3))
    for r in run.rows:
        assert 0.0 <= r.covered <= 1.0
        assert r.intros * 2 <= r.pool
        assert 0.0 <= r.avg_score <= 1.0
    assert run.final_active <= run.total_joined


def test_supply_matters_more_than_the_algorithm():
    balanced = run_policy("weekly_drop", SimParams(n=160, weeks=4, pct_women=0.5, pct_nonbinary=0.0,
                                                   cities=[("Bengaluru", 1.0)]))
    skewed = run_policy("weekly_drop", SimParams(n=160, weeks=4, pct_women=0.3, pct_nonbinary=0.0,
                                                 cities=[("Bengaluru", 1.0)]))
    assert np.mean([r.covered for r in balanced.rows]) > np.mean([r.covered for r in skewed.rows]) + 0.1
    top = skewed.supply[0]
    assert top["seeking"] == ["woman"]      # the report points at the missing side


def test_a_higher_floor_trades_coverage_for_quality():
    pts = frontier(SimParams(n=120, weeks=3, seed=2), [0.55, 0.65, 0.75])
    assert pts[0]["covered"] >= pts[1]["covered"] >= pts[2]["covered"]
    assert pts[0]["avg_score"] <= pts[1]["avg_score"] <= pts[2]["avg_score"]


def test_yes_probability_is_monotonic_and_random_draws_are_stable():
    xs = [p_yes(s) for s in (0.2, 0.4, 0.55, 0.7, 0.9)]
    assert xs == sorted(xs) and abs(xs[2] - 0.5) < 1e-9
    assert rand01(1, "a", 2) == rand01(1, "a", 2) and rand01(1, "a", 2) != rand01(1, "a", 3)
    assert 0.0 <= rand01(9, "x") < 1.0


# ---- learning ------------------------------------------------------------------------------------
def test_great_feedback_boosts_the_groups_that_scored_well():
    u = make("a")
    note = apply_feedback(u, {"vibe": 0.9, "communication": 0.5, "values_interests": 0.4, "humor": 0.85}, "great", None)
    assert u.weight_mult["vibe"] > 1.0 and u.weight_mult["humor"] > 1.0
    assert "communication" not in u.weight_mult and note


def test_no_with_a_reason_raises_that_group_and_is_clamped():
    u = make("a")
    for _ in range(20):
        apply_feedback(u, {}, "no", "humor")
    assert u.weight_mult["humor"] == MULT_MAX
    u.weight_mult["vibe"] = 0.1
    apply_feedback(u, {"vibe": 0.9}, "great", None)
    assert u.weight_mult["vibe"] >= MULT_MIN


def test_fine_and_unreasoned_no_change_nothing():
    u = make("a")
    assert apply_feedback(u, {"vibe": 0.9}, "fine", None) is None
    assert apply_feedback(u, {"vibe": 0.9}, "no", None) is None
    assert apply_feedback(u, {"vibe": 0.9}, "no", "not a group") is None
    assert u.weight_mult == {}


# ---- questionnaire ---------------------------------------------------------------------------------
def test_every_scenario_maps_to_a_known_trait_and_is_ordered_low_to_high():
    assert {q["dim"] for q in SCENARIOS} == set(SCALE_DIMS)
    for q in SCENARIOS:
        vals = [o[2] for o in q["options"]]
        assert vals == sorted(vals) and len(q["options"]) == 4


def test_traits_from_answers_defaults_to_the_middle():
    t = traits_from_answers({"energy": "d"})
    assert t["energy"] == 0.92 and t["money"] == 0.5 and set(t) == set(SCALE_DIMS)


def test_interest_keywords_fallback():
    got = interests_from_text("Sunday means a long trek, filter coffee and some stand-up on Netflix")
    assert {"trekking", "coffee", "stand-up comedy", "movies"} <= set(got)
    assert interests_from_text("") == []


def test_build_user_cleans_inputs():
    basics = dict(name="  Asha  ", gender="woman", seeking=["man"], age=23, age_min=21, age_max=28,
                  city="Pune", open_distance=False, intent=2)
    u = build_user("x", basics, {}, ["dry", "nonsense", "goofy"], ["coffee", "made up"], ["humor", "x", "vibe", "extra"],
                   extra_interests=["books", "coffee"])
    assert u.name == "Asha" and u.humor == ["dry", "goofy"] and u.interests == ["coffee", "books"]
    assert u.priorities == ["humor", "vibe"]


# ---- language model layer (mocked: no network in tests) -----------------------------------------------
def test_llm_is_off_by_default_and_falls_back(monkeypatch):
    monkeypatch.delenv("AYMORA_LLM", raising=False)
    assert not llm.enabled()
    assert llm.extract_interests("I love hiking", INTERESTS) is None
    assert llm.reword(["You both like coffee."]) is None


def test_llm_output_is_validated(monkeypatch):
    monkeypatch.setenv("AYMORA_LLM", "1")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: 'Sure! ["trekking", "invented tag", "coffee"]')
    assert llm.extract_interests("hiking and chai", INTERESTS) == ["trekking", "coffee"]
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: "not json")
    assert llm.extract_interests("x", INTERESTS) is None
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: '["one", "two"]')
    assert llm.reword(["a", "b", "c"]) is None                      # wrong length is rejected
    assert llm.reword(["a", "b"]) == ["one", "two"]
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: '["' + "x" * 400 + '"]')
    assert llm.reword(["a"]) is None                                 # too long is rejected
