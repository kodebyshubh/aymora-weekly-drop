import numpy as np

from app import compat
from app.cohort import make_cohort
from app.traits import GROUPS, SCALE_DIMS
from tests.helpers import make


def pair_mats(a, b):
    m = compat.build([a, b])
    return m, m.pair(a.id, b.id)


def test_matrices_are_well_formed():
    users = make_cohort(120, seed=3)
    m = compat.build(users)
    assert m.mutual.shape == (120, 120)
    assert np.allclose(m.mutual, m.mutual.T)
    assert (m.eligible == m.eligible.T).all()
    assert not m.eligible.diagonal().any()
    assert m.mutual.min() >= 0.0 and m.mutual.max() <= 1.0
    for g in GROUPS:
        assert np.allclose(m.groups[g], m.groups[g].T)
    assert np.allclose(m.weights.sum(axis=1), 1.0)


def test_identical_people_score_high_and_opposites_low():
    a = make("a", level=0.3)
    twin = make("b", gender="woman", seeking=("man",), level=0.3)
    far = make("c", gender="woman", seeking=("man",), level=0.95, humor=("wholesome",), interests=("pets",))
    a2 = make("a2", level=0.05, humor=("sarcastic",), interests=("gaming",))
    _, close = pair_mats(a, twin)
    _, apart = pair_mats(a2, far)
    assert close["mutual"] > 0.85
    assert apart["mutual"] < 0.45
    assert close["mutual"] > apart["mutual"]


def test_hard_filters():
    base = make("a")
    ok = make("b", gender="woman", seeking=("man",))
    assert pair_mats(base, ok)[1]["eligible"]
    # gender: she does not seek men
    assert not pair_mats(base, make("b", gender="woman", seeking=("woman",)))[1]["eligible"]
    # wrong gender for him
    assert not pair_mats(base, make("b", gender="man", seeking=("man",)))[1]["eligible"]
    # age: he is 24, her range stops at 22
    assert not pair_mats(base, make("b", gender="woman", seeking=("man",), age_min=18, age_max=22))[1]["eligible"]
    # city
    assert not pair_mats(base, make("b", gender="woman", seeking=("man",), city="Pune"))[1]["eligible"]
    both_open_a = make("a", open_distance=True)
    assert pair_mats(both_open_a, make("b", gender="woman", seeking=("man",), city="Pune", open_distance=True))[1]["eligible"]
    # one open, one not: still blocked
    assert not pair_mats(both_open_a, make("b", gender="woman", seeking=("man",), city="Pune"))[1]["eligible"]
    # intent two steps apart
    assert not pair_mats(make("a", intent=0), make("b", gender="woman", seeking=("man",), intent=2))[1]["eligible"]


def test_history_blocks_repeat_introductions():
    a, b = make("a"), make("b", gender="woman", seeking=("man",))
    assert pair_mats(a, b)[1]["eligible"]
    a.history.add("b")
    assert not pair_mats(a, b)[1]["eligible"]


def test_inactive_people_are_out_of_the_pool():
    a, b = make("a"), make("b", gender="woman", seeking=("man",))
    b.active = False
    assert not pair_mats(a, b)[1]["eligible"]


def test_intent_gap_of_one_costs_a_little():
    same = pair_mats(make("a", intent=1), make("b", gender="woman", seeking=("man",), intent=1))[1]["mutual"]
    off = pair_mats(make("a", intent=1), make("b", gender="woman", seeking=("man",), intent=2))[1]["mutual"]
    assert off < same


def test_priorities_change_directional_weights_not_the_pair_groups():
    a = make("a", level=0.2, humor=("dry",))
    b = make("b", gender="woman", seeking=("man",), level=0.2, humor=("wholesome",))
    m0 = compat.build([a, b])
    a.priorities = ["humor", "humor"]
    m1 = compat.build([a, b])
    # same group scores, but a now weighs humor more, and humor is the weak spot here
    assert np.allclose(m0.groups["humor"], m1.groups["humor"])
    assert m1.weights[0][GROUPS.index("humor")] > m0.weights[0][GROUPS.index("humor")]
    assert m1.directional[0, 1] < m0.directional[0, 1]


def test_spontaneity_rewards_a_small_gap():
    a = make("a", spontaneity=0.4)
    same = make("b", gender="woman", seeking=("man",), spontaneity=0.4)
    near = make("c", gender="woman", seeking=("man",), spontaneity=0.65)
    far = make("d", gender="woman", seeking=("man",), spontaneity=1.0)
    s_same = compat.dim_similarity(a, same, "spontaneity")
    s_near = compat.dim_similarity(a, near, "spontaneity")
    s_far = compat.dim_similarity(a, far, "spontaneity")
    assert s_near > s_same > s_far


def test_rare_shared_interest_counts_more_than_a_common_one():
    crowd = [make(f"x{i}", interests=("coffee",)) for i in range(30)] + [make("rare1", interests=("birdwatching",))]
    common_a = make("a", interests=("coffee",))
    common_b = make("b", gender="woman", seeking=("man",), interests=("coffee",))
    rare_a = make("c", interests=("birdwatching",))
    rare_b = make("d", gender="woman", seeking=("man",), interests=("birdwatching",))
    users = crowd + [common_a, common_b, rare_a, rare_b]
    m = compat.build(users)
    assert m.groups["values_interests"][m.index["c"], m.index["d"]] >= m.groups["values_interests"][m.index["a"], m.index["b"]]


def test_empty_interests_are_neutral_not_a_crash():
    a = make("a", interests=())
    b = make("b", gender="woman", seeking=("man",), interests=("coffee",))
    m, p = pair_mats(a, b)
    assert 0.0 <= p["mutual"] <= 1.0


def test_calibration_anchors():
    assert float(compat.calibrate(compat.CALIB_CENTER)) == 0.5
    assert float(compat.calibrate(0.0)) == 0.0 and float(compat.calibrate(1.0)) == 1.0


def test_all_traits_in_unit_range_for_synthetic_people():
    for u in make_cohort(200, seed=5):
        assert all(0.0 <= u.traits[d] <= 1.0 for d in SCALE_DIMS)
        assert 1 <= len(u.humor) <= 2 and u.interests
