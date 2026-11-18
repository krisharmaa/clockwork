"""Saved timetables: create / edit / duplicate / delete data, optimise, edit the schedule by hand, publish."""
import copy
import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def env():
    old_db, old_runs = os.environ.get("CLOCKWORK_DB"), os.environ.get("CLOCKWORK_RUNS_DIR")
    tmp = tempfile.mkdtemp()
    os.environ["CLOCKWORK_DB"] = os.path.join(tmp, "timetables.db")
    os.environ["CLOCKWORK_RUNS_DIR"] = os.path.join(tmp, "runs")
    from api.campus.db import init_db
    from api.server import app
    init_db()
    client = TestClient(app)
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    admin = {"Authorization": f"Bearer {r.json()['token']}"}
    yield client, admin
    for key, value in (("CLOCKWORK_DB", old_db), ("CLOCKWORK_RUNS_DIR", old_runs)):
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def small_department():
    return {
        "name": "Mini department",
        "grid": {"days": ["Mon", "Tue", "Wed"], "periods": ["9", "10", "11", "12", "1", "2"], "lunchPeriod": 3},
        "groups": [{"id": "g1", "name": "Year 1", "strength": 40}],
        "faculty": [{"id": "t1", "name": "Prof. A", "maxWeekly": 10, "maxDaily": 4},
                    {"id": "t2", "name": "Prof. B", "maxWeekly": 10, "maxDaily": 4}],
        "rooms": [{"id": "r1", "name": "Room 1", "capacity": 50, "type": "classroom"},
                  {"id": "r2", "name": "Lab 1", "capacity": 50, "type": "lab"}],
        "offerings": [
            {"id": "c1", "code": "MATH", "subject": "Maths", "type": "theory", "sessionsPerWeek": 3, "groupIds": ["g1"], "eligibleFaculty": ["t1", "t2"]},
            {"id": "c2", "code": "PHY", "subject": "Physics", "type": "theory", "sessionsPerWeek": 2, "groupIds": ["g1"], "eligibleFaculty": ["t2"]},
            {"id": "c3", "code": "LAB", "subject": "Lab", "type": "lab", "sessionsPerWeek": 1, "duration": 2, "groupIds": ["g1"], "eligibleFaculty": ["t1"]},
        ],
    }


def run_saved(client, admin, tid, budget=60):
    r = client.post("/api/runs", json={"scenario": "saved", "timetableId": tid, "budget": budget, "population": 8,
                                       "searchSeconds": None, "compareBaseline": False}, headers=admin)
    assert r.status_code == 200, r.text
    for _ in range(600):
        st = client.get(f"/api/runs/{r.json()['runId']}", headers=admin).json()
        if st["status"] != "running":
            break
        time.sleep(0.05)
    assert st["status"] == "done", st.get("error")
    return st["result"]


def test_cold_start_and_templates(env):
    client, admin = env
    rows = client.get("/api/timetables", headers=admin).json()
    assert any(r["name"] == "Demo department" for r in rows)  # editable default, not hard-coded
    for template in ("blank", "small"):
        r = client.post("/api/timetables", json={"name": f"From {template}", "template": template}, headers=admin)
        assert r.status_code == 200, r.text
    assert client.post("/api/timetables", json={"template": "published"}, headers=admin).status_code == 409
    assert client.post("/api/timetables", json={"template": "nope"}, headers=admin).status_code == 400


def test_create_edit_optimise_edit_by_hand_publish(env):
    client, admin = env
    tid = client.post("/api/timetables", json={"name": "Mini", "template": "blank"}, headers=admin).json()["id"]
    # optimising an empty timetable is refused with a clear message
    assert client.post("/api/runs", json={"scenario": "saved", "timetableId": tid}, headers=admin).status_code == 400
    # fill in the data
    r = client.put(f"/api/timetables/{tid}", json={"instance": small_department()}, headers=admin)
    assert r.status_code == 200, r.text
    inst = r.json()["instance"]
    assert len(inst["events"]) == 6 and r.json()["warnings"] == []
    # invalid data is refused with the reason
    bad = small_department()
    bad["offerings"][0]["eligibleFaculty"] = ["ghost"]
    assert client.put(f"/api/timetables/{tid}", json={"instance": bad}, headers=admin).status_code == 400
    # warnings explain impossible data
    hard = small_department()
    hard["rooms"] = [hard["rooms"][0]]
    assert any("no lab" in w for w in client.put(f"/api/timetables/{tid}", json={"instance": hard}, headers=admin).json()["warnings"])
    client.put(f"/api/timetables/{tid}", json={"instance": small_department()}, headers=admin)

    res = run_saved(client, admin, tid)
    assert res["instance"]["name"] == "Mini"
    best = next(s for s in res["solutions"] if s["onFront"])
    assert client.put(f"/api/timetables/{tid}/schedule", json={"solution": best}, headers=admin).status_code == 200
    got = client.get(f"/api/timetables/{tid}", headers=admin).json()
    assert got["schedule"] == "ok" and got["check"]["feasible"]

    # edit by hand: put two MATH sessions at the same time -> clash is reported and cannot be saved
    sol = copy.deepcopy(got["solution"])
    maths = [a for a in sol["assignments"] if a["eventId"].startswith("c1")]
    maths[1].update(day=maths[0]["day"], period=maths[0]["period"])
    chk = client.post(f"/api/timetables/{tid}/check", json={"solution": sol}, headers=admin).json()
    assert not chk["feasible"] and chk["violations"]
    assert client.put(f"/api/timetables/{tid}/schedule", json={"solution": sol}, headers=admin).status_code == 400
    # a valid manual move (found with the same check the editor uses) is accepted
    original = got["solution"]
    moved = None
    for idx, a in enumerate(original["assignments"]):
        for d in range(3):
            for p in range(6):
                if (d, p) == (a["day"], a["period"]):
                    continue
                trial = copy.deepcopy(original)
                trial["assignments"][idx].update(day=d, period=p)
                if client.post(f"/api/timetables/{tid}/check", json={"solution": trial}, headers=admin).json()["feasible"]:
                    moved = trial
                    break
            if moved:
                break
        if moved:
            break
    assert moved is not None
    assert client.put(f"/api/timetables/{tid}/schedule", json={"solution": moved}, headers=admin).status_code == 200
    assert client.get(f"/api/timetables/{tid}", headers=admin).json()["solution"]["assignments"] == moved["assignments"]

    # publish the saved timetable
    assert client.post(f"/api/timetables/{tid}/publish", headers=admin).status_code == 200
    assert client.get("/api/timetable", headers=admin).json()["instance"]["name"] == "Mini"

    # changing the data keeps the schedule attached to the classes that still exist
    data = client.get(f"/api/timetables/{tid}", headers=admin).json()["instance"]
    data["offerings"] = [o for o in data["offerings"] if o["id"] != "c2"]
    r = client.put(f"/api/timetables/{tid}", json={"instance": data}, headers=admin).json()
    assert r["check"]["exists"] and r["check"]["unplaced"] == [] and len(r["instance"]["events"]) == 4
    data["offerings"][0]["sessionsPerWeek"] = 4  # one more MATH session -> one class to place
    r = client.put(f"/api/timetables/{tid}", json={"instance": data}, headers=admin).json()
    assert len(r["check"]["unplaced"]) == 1
    assert client.put(f"/api/timetables/{tid}/schedule", json={"solution": r["instance"] and client.get(f"/api/timetables/{tid}", headers=admin).json()["solution"]}, headers=admin).status_code == 400


def test_duplicate_delete_and_save_from_run(env):
    client, admin = env
    rows = client.get("/api/timetables", headers=admin).json()
    demo = next(r for r in rows if r["name"] == "Demo department")
    copy_id = client.post(f"/api/timetables/{demo['id']}/duplicate", headers=admin).json()["id"]
    assert client.get(f"/api/timetables/{copy_id}", headers=admin).json()["name"] == "Demo department (copy)"
    client.put(f"/api/timetables/{copy_id}", json={"name": "Renamed"}, headers=admin)
    assert client.get(f"/api/timetables/{copy_id}", headers=admin).json()["name"] == "Renamed"
    assert client.delete(f"/api/timetables/{copy_id}", headers=admin).status_code == 200
    assert client.get(f"/api/timetables/{copy_id}", headers=admin).status_code == 404
    # save a run's final timetable as a new saved timetable
    res = run_saved(client, admin, demo["id"])
    best = next(s for s in res["solutions"] if s["onFront"])
    tid = client.post("/api/timetables", json={"name": "Final from run", "template": "data", "instance": res["instance"], "solution": best},
                      headers=admin).json()["id"]
    assert client.get(f"/api/timetables/{tid}", headers=admin).json()["schedule"] == "ok"
    # non-admins cannot manage timetables
    assert client.get("/api/timetables").status_code == 401


def test_starter_is_current_timetable_before_any_run(env):
    client, admin = env
    s = client.get("/api/starter", headers=admin).json()
    # this module publishes "Mini" earlier, so the current timetable is the published one
    assert s["kind"] == "published" and s["instance"]["name"] == "Mini" and s["check"]["feasible"]
    assert client.get("/api/starter").status_code == 401


def test_starter_without_published_is_an_unoptimised_start(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOCKWORK_DB", str(tmp_path / "fresh.db"))
    from api.campus.db import init_db
    from api.server import app
    init_db()
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()["token"]}
    s = c.get("/api/starter", headers=h).json()
    assert s["kind"] == "starting" and s["name"] == "Demo department" and s["timetableId"]
    assert s["check"]["feasible"] and len(s["solution"]["assignments"]) == len(s["instance"]["events"])
