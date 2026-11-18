"""Deterministic browser regressions for failed and out-of-order API responses.

Run against the Vite development server with Python Playwright installed:
  python frontend/tests/browser_failure_regression.py http://127.0.0.1:5173
All /api requests are intercepted; this never mutates the running API database.
"""
from __future__ import annotations

import argparse
import shutil
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url", nargs="?", help="Vite development URL (also accepted as --web)")
parser.add_argument("--web", help="Vite development URL")
parser.add_argument("--artifacts", default="/tmp/clockwork-browser", help="Screenshot output directory")
args = parser.parse_args()
URL = (args.web or args.url or "http://127.0.0.1:5173").rstrip("/")
ARTIFACTS = Path(args.artifacts)
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def instance(lunches):
    return {
        "name": "Workflow regression", "grid": {"days": ["Mon", "Tue"],
        "periods": ["Morning", "Break", "Afternoon", "Meal"],
        "lunchPeriod": lunches[0] if lunches else -1, "lunchPeriods": lunches},
        "groups": [{"id": "g1", "name": "Class 1", "strength": 20}],
        "faculty": [{"id": f"f{i}", "name": f"Teacher {i}", "maxWeekly": 20, "maxDaily": 4} for i in (1, 2)],
        "rooms": [{"id": "r1", "name": "Room 1", "capacity": 30, "type": "classroom"}],
        "offerings": [{"id": "o1", "code": "TEST", "subject": "Regression", "groupIds": ["g1"],
                       "type": "theory", "sessionsPerWeek": 2, "eligibleFaculty": ["f1", "f2"]}],
        "events": [{"id": f"e{i}", "offeringId": "o1", "length": 1, "headcount": 20} for i in (1, 2)],
    }


def wait_until(page, condition):
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline, "Timed out waiting for intercepted request"
        page.wait_for_timeout(10)


def run():
    state = {"hold_constraints": True, "pending": [], "writes": [], "fail_pub": False, "lunches": [1, 3],
             "hold_decision": False, "decisions": []}
    failures = []

    def respond(route, value, status=200):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(value))

    def dispatch(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix("/api")
        inst = instance(state["lunches"])
        if path == "/timetable":
            if state["fail_pub"]:
                return respond(route, {"detail": "Timetable service offline"}, 503)
            return respond(route, {"instance": inst, "solution": {"id": "P1", "objectives": {"f1": 0, "f2": .2, "f3": 0},
                "facultyOf": {"o1": "f1"}, "assignments": [{"eventId": "e1", "day": 0, "period": 0, "roomId": "r1"},
                {"eventId": "e2", "day": 0, "period": 2, "roomId": "r1"}]},
                "design": None, "publishedAt": "2026-11-14T12:00:00Z", "publishedBy": "admin"})
        if path == "/constraints" and state["hold_constraints"]:
            state["pending"].append(route)
            return
        if path.startswith("/constraints/"):
            state["writes"].append((path, request.post_data_json))
            return respond(route, {"conflicts": 0})
        if path == "/constraints":
            return respond(route, {})
        if path == "/mcdm":
            if state["hold_decision"]:
                state["decisions"].append(route)
                return
            return respond(route, decision(request.post_data_json))
        if path == "/leaves":
            return respond(route, [{"id": 1, "faculty_id": "f1", "start_date": "2026-11-16", "end_date": "2026-11-16", "reason": "Test leave"}])
        if path == "/leaves/1":
            return respond(route, {"detail": "Leave removal rejected"}, 409)
        if path == "/calendar":
            monday = parse_qs(parsed.query)["start"][0]
            return respond(route, {"published": True, "semester": {"start": "2020-01-01", "end": "2099-12-31"},
                "days": inst["grid"]["days"], "periods": inst["grid"]["periods"], "lunchPeriod": inst["grid"]["lunchPeriod"],
                "lunchPeriods": state["lunches"], "holidays": {}, "assessments": [],
                "occurrences": [{"id": f"e{i}@{monday}", "kind": "lecture", "eventId": f"e{i}", "offeringId": "o1",
                    "code": f"TEST-{i}", "subject": "Regression", "date": monday, "day": 0, "period": p, "length": 1,
                    "roomId": "r1", "groupIds": ["g1"], "facultyId": "f1", "originalFacultyId": "f1",
                    "status": "scheduled", "reason": "", "coverOpen": False} for i, p in ((1, 0), (2, 2))]})
        if path == "/free":
            return respond(route, {"teachers": inst["faculty"], "rooms": inst["rooms"], "busyGroups": []})
        if path == "/assessments":
            return respond(route, [{"id": 1, "title": "Custom labels", "day": "2026-11-16", "start_period": 0, "end_period": 2, "group_ids": ["g1"]},
                {"id": 2, "title": "Previous grid", "day": "2026-11-17", "start_period": 0, "end_period": 8, "group_ids": ["g1"]}])
        if path == "/notifications":
            return respond(route, {"unread": 0, "items": []})
        if path == "/disruptions":
            return respond(route, {"items": []})
        if path == "/users":
            return respond(route, [])
        raise AssertionError(f"Unexpected API request: {request.method} {path}")

    def decision(body):
        return {"recommended": 0, "weights": [1 / 3] * 3, "ahp": None, "sensitivity": None,
                "ranking": [{"index": i, "rank": i + 1, "score": .8 - i * .001, "objectives": obj}
                            for i, obj in enumerate(body["objectives"])]}

    with sync_playwright() as pw:
        executable = shutil.which("chromium") or shutil.which("google-chrome")
        browser = pw.chromium.launch(headless=True, **({"executable_path": executable} if executable else {}))
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        user = {"id": 1, "username": "admin", "displayName": "Admin", "role": "admin", "facultyId": None,
                "groupId": None, "defaultPassword": False}
        context.add_init_script("localStorage.setItem('clockwork-auth', " + json.dumps(json.dumps({"state": {"token": "regression-token", "user": user}, "version": 0})) + ");")
        context.route("**/api/**", dispatch)
        context.route("https://fonts.googleapis.com/**", lambda route: route.abort())
        page = context.new_page()
        page.set_default_timeout(7000)
        page.on("pageerror", lambda error: failures.append(str(error)))
        try:
            page.goto(URL + "/#/manage", wait_until="domcontentloaded")
            page.get_by_role("button", name="Availability", exact=True).click()
            wait_until(page, lambda: len(state["pending"]) > 0)
            expect(page.get_by_role("button", name="Save availability")).to_be_disabled()
            old_requests = list(state["pending"])
            page.get_by_label("Availability teacher").select_option("f2")
            wait_until(page, lambda: len(state["pending"]) > len(old_requests))
            state["hold_constraints"] = False
            for pending in state["pending"][len(old_requests):]:
                respond(pending, {"f2": {"unavailable": [0], "maxDaily": 2, "note": "Current teacher 2"}})
            expect(page.get_by_label("Note for the administrator")).to_have_value("Current teacher 2")
            for pending in old_requests:
                respond(pending, {"f1": {"unavailable": [], "maxDaily": 5, "note": "Stale teacher 1"}})
            page.wait_for_timeout(80)
            expect(page.get_by_label("Note for the administrator")).to_have_value("Current teacher 2")
            expect(page.locator(".avail-cell.lunch")).to_have_count(4)
            page.get_by_role("button", name="Save availability").click()
            wait_until(page, lambda: len(state["writes"]) == 1)
            assert state["writes"][0] == ("/constraints/f2", {"unavailable": [0], "maxDaily": 2, "note": "Current teacher 2"})

            page.get_by_role("button", name="Teacher leave", exact=True).click()
            page.get_by_role("button", name="Remove", exact=True).click()
            expect(page.get_by_text("Leave removal rejected", exact=True)).to_be_visible()
            expect(page.get_by_label("Leave start date")).to_be_visible()
            page.get_by_role("button", name="Online assessments", exact=True).click()
            expect(page.get_by_text("Morning–Afternoon", exact=False)).to_be_visible()
            expect(page.get_by_text("Morning–Period 9", exact=False)).to_be_visible()
            expect(page.get_by_label("From").locator("option")).to_have_count(2)
            expect(page.get_by_label("From")).to_have_value("0")
            expect(page.get_by_role("combobox", name=re.compile("^To"))).to_have_value("2")

            page.goto(URL + "/#/calendar", wait_until="domcontentloaded")
            expect(page.locator(".cal-cell.lunch")).to_have_count(4)
            page.locator(".occ").nth(0).click()
            page.get_by_label("Reason (optional)").fill("Must not follow another lecture")
            page.get_by_label("Substitute teacher").select_option("f2")
            page.locator(".occ").nth(1).click()
            expect(page.get_by_label("Reason (optional)")).to_have_value("")
            expect(page.get_by_label("Substitute teacher")).to_have_value("")
            page.get_by_role("button", name="Close", exact=True).click()
            page.locator(".cal-cell.free").nth(0).click()
            page.get_by_label("Title (optional)").fill("Must not follow another slot")
            page.locator(".cal-cell.free").nth(1).click(position={"x": 8, "y": 8})
            expect(page.get_by_label("Title (optional)")).to_have_value("")

            state["lunches"] = []
            page.reload()
            expect(page.get_by_label("Calendar entity")).to_be_visible()
            expect(page.locator(".cal-cell.lunch")).to_have_count(0)

            page.goto(URL + "/#/pareto", wait_until="domcontentloaded")
            expect(page.get_by_text("Recommended", exact=True)).to_be_visible()
            state["hold_decision"] = True
            page.get_by_role("button", name="Students first", exact=True).click()
            expect(page.get_by_text("Ranking the front…", exact=True)).to_be_visible()
            expect(page.get_by_text("Recommended", exact=True)).to_have_count(0)
            wait_until(page, lambda: len(state["decisions"]) > 0)
            for slider in page.get_by_role("slider").all():
                slider.press("Home")
            expect(page.get_by_text("Give at least one objective a weight above zero.", exact=True)).to_be_visible()
            expect(page.get_by_text("Ranking the front…", exact=True)).to_have_count(0)
            for pending in state["decisions"]:
                respond(pending, decision(pending.request.post_data_json))
            page.wait_for_timeout(80)
            expect(page.get_by_text("Recommended", exact=True)).to_have_count(0)

            state["fail_pub"] = True
            page.goto(URL + "/#/calendar", wait_until="domcontentloaded")
            expect(page.get_by_text("Timetable service offline", exact=True)).to_be_visible()
            assert not failures, failures
            page.screenshot(path=str(ARTIFACTS / "publication-error.png"))
            print("PASS: availability race/save isolation, leave failure, custom assessment labels, drawer resets, lunch grids, stale decision ranking/zero weights, publication error; no browser exceptions")
        except Exception:
            page.screenshot(path=str(ARTIFACTS / "failure.png"), full_page=True)
            raise
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    run()
