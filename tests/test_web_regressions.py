"""Small end-to-end regressions for published JSON and dated calendar transitions."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from api.campus.db import connect, init_db
from api.server import app

MONDAY = "2026-11-02"
TUESDAY = "2026-11-03"


@pytest.fixture
def campus(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOCKWORK_DB", str(tmp_path / "campus.db"))
    init_db()
    c = TestClient(app)

    def login(username, password):
        response = c.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['token']}"}

    admin = login("admin", "admin")
    instance = {
        "name": "Calendar regression", "grid": {"days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "periods": ["P1", "P2", "P3", "P4", "Lunch"], "lunchPeriod": 4, "lunchPeriods": [4]},
        "groups": [{"id": "g1", "name": "Group 1", "strength": 10}, {"id": "g2", "name": "Group 2", "strength": 12}],
        "faculty": [{"id": f"f{i}", "name": f"Teacher {i}", "maxWeekly": 10, "maxDaily": 3, "unavailable": []} for i in range(1, 4)],
        "rooms": [{"id": "r1", "name": "Room 1", "capacity": 30, "type": "classroom", "unavailable": []},
                  {"id": "r2", "name": "Room 2", "capacity": 30, "type": "classroom", "unavailable": [3]},
                  {"id": "small", "name": "Small", "capacity": 12, "type": "classroom", "unavailable": []}],
        "offerings": [{"id": f"o{i}", "code": f"C{i}", "subject": f"Course {i}", "groupIds": ["g2" if i == 2 else "g1"],
                       "type": "theory", "sessionsPerWeek": 1, "eligibleFaculty": [f"f{i}"]} for i in range(1, 4)],
        "events": [{"id": f"e{i}", "offeringId": f"o{i}", "length": 1, "headcount": 12 if i == 2 else 10} for i in range(1, 4)],
    }
    solution = {"id": "S", "facultyOf": {f"o{i}": f"f{i}" for i in range(1, 4)}, "assignments": [
        {"eventId": "e1", "day": 0, "period": 0, "roomId": "r1"},
        {"eventId": "e2", "day": 0, "period": 2, "roomId": "r2"},
        {"eventId": "e3", "day": 1, "period": 0, "roomId": "r1"},
    ]}
    body = {"instance": instance, "solution": solution}
    assert c.post("/api/timetable/publish", json=body, headers=admin).status_code == 200
    assert c.put("/api/semester", json={"start": MONDAY, "end": "2026-11-27"}, headers=admin).status_code == 200

    def teacher(fid):
        response = c.post("/api/users", json={"username": fid, "password": "secret", "role": "teacher", "facultyId": fid}, headers=admin)
        assert response.status_code == 200, response.text
        return login(fid, "secret"), response.json()["id"]

    def post(path, body, headers=None, status=200):
        response = c.post(path, json=body, headers=headers or admin)
        assert response.status_code == status, response.text
        return response

    def occurrences(day=MONDAY):
        response = c.get("/api/calendar", params={"start": day, "end": day}, headers=admin)
        assert response.status_code == 200, response.text
        return response.json()["occurrences"]

    return {"client": c, "admin": admin, "body": body, "teacher": teacher, "post": post, "occurrences": occurrences}


@pytest.mark.parametrize("malformation", ["duplicate", "aliased", "fractional", "rows", "faculty", "duplicate_event", "orphan_event"])
def test_publish_rejects_malformed_calendar_json(campus, malformation):
    body = deepcopy(campus["body"])
    if malformation == "duplicate":
        body["solution"]["assignments"].append(body["solution"]["assignments"][0])
    elif malformation == "aliased":
        body["solution"]["assignments"][2].update(day=0, period=5)
    elif malformation == "fractional":
        body["solution"]["assignments"][0]["day"] = 0.2
    elif malformation == "rows":
        body["solution"]["assignments"] = ["bad row"]
    elif malformation == "faculty":
        body["solution"]["facultyOf"] = []
    elif malformation == "duplicate_event":
        body["instance"]["events"][1]["id"] = "e1"
        body["solution"]["assignments"][1]["eventId"] = "e1"
    else:
        body["instance"]["events"][0]["offeringId"] = "missing"
    campus["post"]("/api/timetable/publish", body, status=400)
    assert len(campus["occurrences"]()) == 2


@pytest.mark.parametrize("action", ["restore", "assign", "request", "accept"])
def test_cover_or_restore_rechecks_students_and_room(campus, action):
    post = campus["post"]
    ref = {"eventId": "e1", "date": MONDAY}
    f2, _ = campus["teacher"]("f2")
    rid = post("/api/requests", ref, f2).json()["id"] if action == "accept" else None
    post("/api/lectures/cancel", ref)
    # The original lecture's students now have an extra class in that released slot.
    post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 0, "roomId": "r2"})
    if action in ("restore", "assign"):
        post(f"/api/lectures/{action}", {**ref, "facultyId": "f2"}, status=409)
    elif action == "request":
        post("/api/requests", ref, f2, status=409)
    else:
        post(f"/api/requests/{rid}/accept", {}, status=409)
    lecture = next(o for o in campus["occurrences"]() if o["eventId"] == "e1")
    assert lecture["status"] == "needs_cover"  # rejected writes roll back


def test_removing_leave_cannot_reactivate_a_collision(campus):
    post, c = campus["post"], campus["client"]
    post("/api/leaves", {"facultyId": "f1", "start": MONDAY, "end": MONDAY})
    post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 0, "roomId": "r2"})
    lid = c.get("/api/leaves", headers=campus["admin"]).json()[0]["id"]
    assert c.delete(f"/api/leaves/{lid}", headers=campus["admin"]).status_code == 409
    assert next(o for o in campus["occurrences"]() if o["eventId"] == "e1")["status"] == "needs_cover"


@pytest.mark.parametrize("closure", ["holiday", "assessment", "leave", "syllabus"])
def test_existing_extra_classes_obey_later_calendar_changes(campus, closure):
    post = campus["post"]
    post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 1, "roomId": "r2"})
    if closure == "holiday":
        post("/api/holidays", {"date": MONDAY, "name": "Closed"})
    elif closure == "assessment":
        post("/api/assessments", {"title": "Assessment", "date": MONDAY, "startPeriod": 1, "endPeriod": 1, "groupIds": ["g1"]})
    elif closure == "leave":
        post("/api/leaves", {"facultyId": "f3", "start": MONDAY, "end": MONDAY})
    else:
        post("/api/syllabus", {"offeringId": "o3", "completedOn": "2026-11-01"})
    extras = [o for o in campus["occurrences"]() if o["eventId"] is None]
    if closure == "syllabus":
        assert not extras
    else:
        assert extras and extras[0]["status"] == "cancelled"


def test_substitute_leave_reopens_cover(campus):
    post = campus["post"]
    post("/api/lectures/assign", {"eventId": "e1", "date": MONDAY, "facultyId": "f2"})
    response = post("/api/leaves", {"facultyId": "f2", "start": MONDAY, "end": MONDAY})
    assert response.json()["lecturesNeedingCover"] == 2
    assert next(o for o in campus["occurrences"]() if o["eventId"] == "e1")["status"] == "needs_cover"


def test_extra_capacity_sums_joint_groups(campus):
    body = deepcopy(campus["body"])
    body["instance"]["offerings"][2]["groupIds"] = ["g1", "g2"]
    body["instance"]["events"][2]["headcount"] = 22
    campus["post"]("/api/timetable/publish", body)
    response = campus["post"]("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 1, "roomId": "small"}, status=400)
    assert "22 students" in response.json()["detail"]


def test_free_and_extra_respect_room_unavailability_and_daily_limit(campus):
    c, admin, post = campus["client"], campus["admin"], campus["post"]
    free = c.get("/api/free", params={"date": MONDAY, "period": 3}, headers=admin).json()
    assert "r2" not in {r["id"] for r in free["rooms"]}
    post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 3, "roomId": "r2"}, status=409)
    assert c.put("/api/constraints/f3", json={"unavailable": [], "maxDaily": 1}, headers=admin).status_code == 200
    free = c.get("/api/free", params={"date": TUESDAY, "period": 1}, headers=admin).json()
    assert "f3" not in {f["id"] for f in free["teachers"]}
    post("/api/extra-classes", {"offeringId": "o3", "date": TUESDAY, "period": 1, "roomId": "r2"}, status=409)


@pytest.mark.parametrize("period,length", [(-1, 1), (5, 1), (1, 0), (3, 2)])
def test_free_rejects_non_teaching_spans(campus, period, length):
    response = campus["client"].get("/api/free", params={"date": MONDAY, "period": period, "length": length}, headers=campus["admin"])
    assert response.status_code == 400


def test_multiple_lunch_periods_are_returned_and_checked(campus):
    body = deepcopy(campus["body"])
    body["instance"]["grid"]["lunchPeriods"] = [3, 4]
    campus["post"]("/api/timetable/publish", body)
    response = campus["client"].get("/api/calendar", params={"start": MONDAY, "end": MONDAY}, headers=campus["admin"])
    assert response.json()["lunchPeriods"] == [3, 4]
    campus["post"]("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 3, "roomId": "r1"}, status=400)


def test_request_cannot_be_accepted_by_former_owner_after_republish(campus):
    f1, _ = campus["teacher"]("f1")
    f2, _ = campus["teacher"]("f2")
    rid = campus["post"]("/api/requests", {"eventId": "e1", "date": MONDAY}, f2).json()["id"]
    body = deepcopy(campus["body"])
    body["instance"]["offerings"][0]["eligibleFaculty"] = ["f1", "f3"]
    body["solution"]["facultyOf"]["o1"] = "f3"
    campus["post"]("/api/timetable/publish", body)
    campus["post"](f"/api/requests/{rid}/accept", {}, f1, status=409)


def test_trimmed_duplicate_usernames_return_validation_error(campus):
    campus["teacher"]("f1")
    response = campus["post"]("/api/users", {"username": " f1 ", "password": "secret", "role": "teacher", "facultyId": "f1"}, status=400)
    assert "taken" in response.json()["detail"]
    campus["post"]("/api/users", {"username": "  ", "password": "secret", "role": "admin"}, status=400)


def test_noncanonical_dates_are_rejected_instead_of_saving_inert_changes(campus):
    campus["post"]("/api/holidays", {"date": "20261102", "name": "Closed"}, status=400)
    campus["post"]("/api/lectures/cancel", {"eventId": "e1", "date": "20261102"}, status=400)
    assert next(o for o in campus["occurrences"]() if o["eventId"] == "e1")["status"] == "scheduled"


def test_fast_republication_has_a_distinct_version(campus, monkeypatch):
    # Freeze the old second-resolution helper: each publication still gets its own version.
    monkeypatch.setattr("api.campus.routes.now", lambda: "2026-11-02T00:00:00+00:00")
    c, admin = campus["client"], campus["admin"]
    campus["post"]("/api/timetable/publish", campus["body"])
    first = c.get("/api/timetable", headers=admin).json()["publishedAt"]
    campus["post"]("/api/timetable/publish", campus["body"])
    second = c.get("/api/timetable", headers=admin).json()["publishedAt"]
    assert first != second


def _small_reoptimization(campus):
    import time
    did = campus["post"]("/api/disruptions", {"kind": "room_closed", "resource": "r1"}).json()["id"]
    job = campus["post"](f"/api/disruptions/{did}/reoptimize", {"budget": 10}).json()["jobId"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = campus["client"].get(f"/api/disruption-jobs/{job}", headers=campus["admin"]).json()
        if response["status"] != "running":
            assert response["status"] == "done", response
            return did, response["result"]
        time.sleep(0.01)
    pytest.fail("Small re-optimisation did not finish")


def test_disruption_option_rejects_later_saved_constraints(campus):
    did, result = _small_reoptimization(campus)
    c, admin = campus["client"], campus["admin"]
    before = c.get("/api/timetable", headers=admin).json()["publishedAt"]
    # Another teacher's constraints change without refreshing the room disruption itself.
    assert c.put("/api/constraints/f3", json={"unavailable": [1]}, headers=admin).status_code == 200
    detail = c.get(f"/api/disruptions/{did}", headers=admin).json()
    assert detail["resultStale"] is True
    campus["post"](f"/api/disruptions/{did}/apply", {"option": result["options"][0]["key"]}, status=409)
    assert c.get("/api/timetable", headers=admin).json()["publishedAt"] == before


def test_disruption_option_rejects_fast_republication(campus):
    did, result = _small_reoptimization(campus)
    campus["post"]("/api/timetable/publish", campus["body"])
    campus["post"](f"/api/disruptions/{did}/apply", {"option": result["options"][0]["key"]}, status=409)


def test_room_disruption_rejects_a_day_outside_the_grid(campus):
    campus["post"]("/api/disruptions", {"kind": "room_closed", "resource": "r1", "day": 6}, status=400)


def test_removing_assessment_cannot_reactivate_a_room_collision(campus):
    post, c, admin = campus["post"], campus["client"], campus["admin"]
    post("/api/assessments", {"title": "OA", "date": MONDAY, "startPeriod": 0, "endPeriod": 0, "groupIds": ["g1"]})
    post("/api/extra-classes", {"offeringId": "o2", "date": MONDAY, "period": 0, "roomId": "r1"})
    aid = c.get("/api/assessments", headers=admin).json()[0]["id"]
    assert c.delete(f"/api/assessments/{aid}", headers=admin).status_code == 409
    assert c.get("/api/assessments", headers=admin).json()


def test_removing_long_leave_resolves_its_disruption(campus):
    c, admin = campus["client"], campus["admin"]
    response = campus["post"]("/api/leaves", {"facultyId": "f1", "start": MONDAY, "end": "2026-11-06"}).json()
    did = response["disruption"]["id"]
    lid = c.get("/api/leaves", headers=admin).json()[0]["id"]
    assert c.delete(f"/api/leaves/{lid}", headers=admin).status_code == 200
    assert c.get(f"/api/disruptions/{did}", headers=admin).json()["status"] == "resolved"


def test_old_disruption_descriptions_survive_a_smaller_grid(campus):
    post, c, admin = campus["post"], campus["client"], campus["admin"]
    body = deepcopy(campus["body"])
    body["solution"]["assignments"][0]["day"] = 4
    post("/api/timetable/publish", body)
    did = post("/api/disruptions", {"kind": "room_closed", "resource": "r1", "day": 4}).json()["id"]
    body["solution"]["assignments"][0]["day"] = 0
    body["instance"]["grid"]["days"] = ["Mon", "Tue"]
    post("/api/timetable/publish", body)
    response = c.get("/api/disruptions", headers=admin)
    assert response.status_code == 200, response.text
    assert next(d for d in response.json()["items"] if d["id"] == did)["status"] == "resolved"


def test_disruption_job_discards_result_if_constraints_change_during_work(campus, monkeypatch):
    import threading
    import time
    import api.disruptions as disruptions

    entered, release = threading.Event(), threading.Event()
    optimize = disruptions.epsilon_reoptimize

    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return optimize(*args, **kwargs)

    monkeypatch.setattr(disruptions, "epsilon_reoptimize", paused)
    did = campus["post"]("/api/disruptions", {"kind": "room_closed", "resource": "r1"}).json()["id"]
    job = campus["post"](f"/api/disruptions/{did}/reoptimize", {"budget": 10}).json()["jobId"]
    c, admin = campus["client"], campus["admin"]
    try:
        assert entered.wait(5)
        assert c.put("/api/constraints/f3", json={"unavailable": [1]}, headers=admin).status_code == 200
    finally:
        release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = c.get(f"/api/disruption-jobs/{job}", headers=admin).json()
        if status["status"] != "running":
            break
        time.sleep(0.01)
    assert status["status"] == "error", status
    assert "changed" in status["error"]
    assert c.get(f"/api/disruptions/{did}", headers=admin).json()["result"] is None


def test_optimizer_done_means_result_is_already_persisted(campus, monkeypatch):
    import threading
    import time
    import api.server as server

    entered, release = threading.Event(), threading.Event()
    store = server._store_run

    def paused(*args):
        entered.set()
        assert release.wait(5)
        store(*args)

    monkeypatch.setattr(server, "_store_run", paused)
    response = campus["post"]("/api/runs", {"scenario": "custom", "instance": campus["body"]["instance"],
                                            "budget": 10, "population": 2, "searchSeconds": 1, "compareBaseline": False})
    job = response.json()["runId"]
    c, admin = campus["client"], campus["admin"]
    try:
        assert entered.wait(5)
        assert c.get(f"/api/runs/{job}", headers=admin).json()["status"] == "running"
    finally:
        release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = c.get(f"/api/runs/{job}", headers=admin).json()
        if status["status"] != "running":
            break
        time.sleep(0.01)
    assert status["status"] == "done", status
    assert c.get("/api/runs/latest", headers=admin).json()["runId"] == job


def test_extra_classes_respect_weekly_load_across_days(campus):
    body = deepcopy(campus["body"])
    body["instance"]["faculty"][2]["maxWeekly"] = 1
    campus["post"]("/api/timetable/publish", body)
    # Tuesday's published lecture consumes f3's weekly allowance before Monday's extra is added.
    response = campus["post"]("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 1, "roomId": "r2"}, status=409)
    assert "weekly limit" in response.json()["detail"]
    free = campus["client"].get("/api/free", params={"date": MONDAY, "period": 1}, headers=campus["admin"]).json()
    assert "f3" not in {teacher["id"] for teacher in free["teachers"]}


def test_substitute_counts_toward_weekly_load_but_cancelled_lecture_does_not(campus):
    body = deepcopy(campus["body"])
    body["instance"]["faculty"][1]["maxWeekly"] = 1
    post = campus["post"]
    post("/api/timetable/publish", body)
    target = {"eventId": "e1", "date": MONDAY, "facultyId": "f2"}
    response = post("/api/lectures/assign", target, status=409)
    assert "weekly limit" in response.json()["detail"]
    post("/api/lectures/cancel", {"eventId": "e2", "date": MONDAY})
    post("/api/lectures/assign", target)
    # The cover now occupies the allowance released by the cancelled lecture.
    response = post("/api/extra-classes", {"offeringId": "o2", "date": TUESDAY, "period": 1, "roomId": "r2"}, status=409)
    assert "weekly limit" in response.json()["detail"]


@pytest.mark.parametrize("closure", ["cancel", "holiday", "leave", "assessment", "substitution"])
def test_inactive_or_reassigned_lectures_release_weekly_load(campus, closure):
    body = deepcopy(campus["body"])
    body["instance"]["faculty"][2]["maxWeekly"] = 1
    post = campus["post"]
    post("/api/timetable/publish", body)
    if closure == "cancel":
        post("/api/lectures/cancel", {"eventId": "e3", "date": TUESDAY})
    elif closure == "holiday":
        post("/api/holidays", {"date": TUESDAY, "name": "Closed"})
    elif closure == "leave":
        post("/api/leaves", {"facultyId": "f3", "start": TUESDAY, "end": TUESDAY})
    elif closure == "assessment":
        post("/api/assessments", {"date": TUESDAY, "title": "OA", "groupIds": ["g1"], "startPeriod": 0, "endPeriod": 0})
    else:
        post("/api/lectures/assign", {"eventId": "e3", "date": TUESDAY, "facultyId": "f1"})
    post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 1, "roomId": "r2"})


def test_weekly_load_starts_a_new_allowance_on_monday(campus):
    body = deepcopy(campus["body"])
    body["instance"]["faculty"][2]["maxWeekly"] = 2
    post = campus["post"]
    post("/api/timetable/publish", body)
    # Each week has its own Tuesday lecture plus one dated extra.
    post("/api/extra-classes", {"offeringId": "o3", "date": "2026-11-06", "period": 1, "roomId": "r2"})
    post("/api/extra-classes", {"offeringId": "o3", "date": "2026-11-09", "period": 1, "roomId": "r2"})
    response = post("/api/extra-classes", {"offeringId": "o3", "date": "2026-11-09", "period": 2, "roomId": "r1"}, status=409)
    assert "weekly limit" in response.json()["detail"]


def test_weekly_load_counts_teaching_periods_and_ignores_the_reassigned_occurrence(campus):
    body = deepcopy(campus["body"])
    body["instance"]["faculty"][2]["maxWeekly"] = 2
    body["instance"]["events"][2]["length"] = 2
    post = campus["post"]
    post("/api/timetable/publish", body)
    response = post("/api/extra-classes", {"offeringId": "o3", "date": MONDAY, "period": 1, "roomId": "r2"}, status=409)
    assert "weekly limit" in response.json()["detail"]
    # Reassigning the existing two-period lecture to its current teacher adds no load.
    post("/api/lectures/assign", {"eventId": "e3", "date": TUESDAY, "facultyId": "f3"})
    post("/api/lectures/assign", {"eventId": "e3", "date": TUESDAY, "facultyId": "f3"})
