from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ANSWERS = {q: "c" for q in ["energy", "spontaneity", "chronotype", "openness", "conflict", "reply_style",
                            "ambition", "family", "tradition", "money"]}


def profile(**over):
    body = {
        "basics": {"name": "Asha", "gender": "woman", "seeking": ["man"], "age": 23, "age_min": 21, "age_max": 28,
                   "city": "Bengaluru", "open_distance": False, "intent": 1},
        "answers": ANSWERS, "humor": ["goofy", "referential"], "interests": ["travel", "food", "coffee"],
        "priorities": ["humor", "vibe"], "about": "Sundays are for a long trek and filter coffee.",
    }
    body.update(over)
    return body


def test_health_and_questionnaire():
    assert client.get("/api/health").json() == {"ok": True, "llm": False}
    q = client.get("/api/questionnaire").json()
    assert len(q["scenarios"]) == 10 and len(q["humor"]) == 5
    assert q["survey"]["weights"]["vibe"] == 73.0 and q["survey"]["physical_appearance"] == 27.0
    # the answer key must never leak the trait values
    assert "value" not in str(q["scenarios"][0])


def test_full_visitor_journey():
    r = client.post("/api/profile", json=profile())
    assert r.status_code == 200
    sid = r.json()["sid"]
    assert "trekking" in r.json()["added_interests"]            # pulled from the free text

    v = client.get(f"/api/drop/{sid}").json()
    assert v["week"] == 1 and v["pool"] > 200
    intro = v["intro"]
    assert intro and intro["status"] == "pending" and intro["other"]["full_name"] is None
    assert intro["other"]["bio"] is None                       # privacy by default until mutual
    assert 0 < intro["score"] <= 1 and intro["explain"]["reasons"]

    v = client.post(f"/api/drop/{sid}/respond", json={"action": "in"}).json()
    assert v["intro"]["you"] == "in" and v["intro"]["status"] in ("mutual", "closed")
    if v["intro"]["status"] == "mutual":
        assert v["intro"]["other"]["full_name"] and v["intro"]["other"]["bio"]

    # answering twice is refused
    assert client.post(f"/api/drop/{sid}/respond", json={"action": "pass"}).status_code == 400

    v = client.post(f"/api/drop/{sid}/feedback", json={"rating": "great"}).json()
    assert v["intro"]["feedback_given"]
    assert client.post(f"/api/drop/{sid}/feedback", json={"rating": "great"}).status_code == 400

    v = client.post(f"/api/drop/{sid}/next-week").json()
    assert v["week"] == 2 and v["log"][0]["week"] == 1
    if v["intro"]:
        assert v["intro"]["other"]["first_name"] != v["log"][0].get("name")   # never the same person twice


def test_passing_closes_the_introduction():
    sid = client.post("/api/profile", json=profile()).json()["sid"]
    v = client.post(f"/api/drop/{sid}/respond", json={"action": "pass"}).json()
    assert v["intro"]["status"] == "closed" and v["intro"]["you"] == "pass"
    note = client.post(f"/api/drop/{sid}/feedback", json={"rating": "no", "reason": "humor"}).json()["note"]
    assert note and "humor" in note
    assert client.get(f"/api/drop/{sid}").json()["weights"]["humor"] > 0


def test_visitors_are_isolated_from_each_other():
    a = client.post("/api/profile", json=profile()).json()["sid"]
    first = client.get(f"/api/drop/{a}").json()["intro"]["other"]["first_name"]
    for _ in range(3):
        client.post("/api/profile", json=profile())
    assert client.get(f"/api/drop/{a}").json()["intro"]["other"]["first_name"] == first


def test_someone_nobody_fits_is_told_why():
    body = profile()
    body["basics"].update(city="Pune", gender="nonbinary", seeking=["nonbinary"], age_min=40, age_max=45, age=42)
    sid = client.post("/api/profile", json=body).json()["sid"]
    v = client.get(f"/api/drop/{sid}").json()
    assert v["intro"] is None and v["unmatched"]["reason"] == "no_eligible"
    assert "supply" in v["unmatched"]["text"]
    assert client.post(f"/api/drop/{sid}/respond", json={"action": "in"}).status_code == 400


def test_validation_and_unknown_sessions():
    assert client.get("/api/drop/nope").status_code == 404
    bad = profile()
    bad["basics"]["age_min"], bad["basics"]["age_max"] = 30, 20
    assert client.post("/api/profile", json=bad).status_code == 422
    bad = profile()
    bad["basics"]["gender"] = "robot"
    assert client.post("/api/profile", json=bad).status_code == 422
    bad = profile()
    bad["basics"]["city"] = "Atlantis"
    assert client.post("/api/profile", json=bad).status_code == 422
    assert client.post("/api/profile", json=profile(humor=[])).status_code == 422
    assert client.post("/api/sim", json={"n": 5000}).status_code == 422
    sid = client.post("/api/profile", json=profile()).json()["sid"]
    assert client.post(f"/api/drop/{sid}/respond", json={"action": "marry"}).status_code == 400


def test_simulation_endpoint_shape_and_caching():
    body = {"n": 100, "weeks": 3, "seed": 21}
    r = client.post("/api/sim", json=body)
    assert r.status_code == 200
    d = r.json()
    assert set(d["policies"]) == {"greedy", "one_shot", "weekly_drop"}
    for p in d["policies"].values():
        assert len(p["rows"]) == 3 and 0 <= p["retention"] <= 1
    assert client.post("/api/sim", json=body).json() == d
    f = client.post("/api/frontier", json=body).json()["points"]
    assert len(f) == 6 and f[0]["covered"] >= f[-1]["covered"]


def test_index_serves_the_real_page():
    r = client.get("/")
    assert r.status_code == 200 and "Weekly Drop" in r.text and "/static/app.js" in r.text
    assert client.get("/static/app.js").status_code == 200


def _mutual_session():
    for _ in range(6):
        sid = client.post("/api/profile", json=profile()).json()["sid"]
        for _ in range(8):
            v = client.get(f"/api/drop/{sid}").json()
            if v["intro"] and v["intro"]["status"] == "pending":
                v = client.post(f"/api/drop/{sid}/respond", json={"action": "in"}).json()
            if v["intro"] and v["intro"]["status"] == "mutual":
                return sid
            client.post(f"/api/drop/{sid}/next-week")
    raise AssertionError("no mutual introduction")


def test_staged_reveal_closure_and_report_over_the_api():
    sid = _mutual_session()
    assert client.post(f"/api/drop/{sid}/reveal", json={"step": "numbers"}).status_code == 400
    v = client.post(f"/api/drop/{sid}/reveal", json={"step": "photos"}).json()
    assert v["intro"]["reveal"]["photos"] in ("open", "declined")
    r = client.post(f"/api/drop/{sid}/outcome", json={"kind": "closed", "reason": "humor"}).json()
    assert r["note"] and r["intro"]["outcome"]["kind"] == "closed"
    assert client.post(f"/api/drop/{sid}/outcome", json={"kind": "met"}).status_code == 400
    assert client.post(f"/api/drop/{sid}/outcome", json={"kind": "dance"}).status_code == 400
    r = client.post(f"/api/drop/{sid}/report", json={"reason": "Asked for money"}).json()
    assert r["intro"]["reported"]
    assert client.post(f"/api/drop/{sid}/report", json={}).status_code == 400
    assert client.get(f"/api/drop/{sid}/levers").json()["levers"] is not None


def test_scam_demo_and_boundaries_over_the_api():
    body = profile()
    body["basics"].update(campus="DSCE", private=True, strict_intent=True, verified_only=True)
    sid = client.post("/api/profile", json=body).json()["sid"]
    v = client.get(f"/api/drop/{sid}").json()
    assert v["profile"]["private"] and v["profile"]["campus"] == "DSCE" and v["held_back"]["total"] > 0
    v = client.post(f"/api/drop/{sid}/demo-scam").json()
    assert v["intro"]["other"]["watch"] and v["intro"]["other"]["new_account"]
    body["basics"]["campus"] = "Mars"
    assert client.post("/api/profile", json=body).status_code == 422


def test_engine_room_endpoints_have_the_right_shape():
    body = {"n": 60, "weeks": 2, "seed": 5, "one_city": True}
    p = client.post("/api/promise", json=body).json()
    assert {"headline", "people", "attention", "swipe", "levers", "weekly"} <= set(p)
    assert p["headline"]["ceiling"] >= p["headline"]["delivered"] - 1e-9
    rt = client.post("/api/redteam", json={**body, "adv_pct": 0.08}).json()
    assert [m["name"] for m in rt["modes"]][0] == "No defence" and rt["benchmark"]
    cl = client.post("/api/closure", json=body).json()
    assert len(cl["modes"]) == 2
    s = client.post("/api/sim", json={**body, "realistic": True}).json()
    assert s["params"]["realistic"] is True
