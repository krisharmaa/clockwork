"""Certificates validate generated data independently of optimization success."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from timetable.evaluation import evaluate
from timetable.generation import generate_instance
from timetable.model import problem_to_dict, schedule_to_dict


@pytest.mark.parametrize("size,events,groups,rooms,faculty", [
    ("small", 40, 2, 5, 6), ("medium", 150, 8, 12, 20),
    ("large", 400, 20, 25, 50),
])
def test_presets_have_independent_feasibility_certificates(size, events, groups, rooms, faculty):
    for seed in (0, 1, 19):
        problem, certificate = generate_instance(size, seed)
        result = evaluate(problem, certificate)
        assert result.feasible, result.violations
        assert len(problem.events) == events
        assert len(problem.groups) == groups
        assert len(problem.rooms) == rooms
        assert len(problem.faculty) == faculty
        assert len(certificate.placements) == events
        assert problem.metadata["synthetic"] is True
        # The serialized instance contains no planted schedule or teacher choice.
        assert "certificate" not in problem_to_dict(problem)
        assert "placements" not in problem_to_dict(problem)
        represented = {f for k in problem.offerings for f in k.eligible_faculty}
        assert represented == {f.id for f in problem.faculty}
        assert all(len(k.eligible_faculty) >= 2 for k in problem.offerings)


def test_generator_reproducibility_uses_local_seed():
    first, witness1 = generate_instance("small", 17)
    second, witness2 = generate_instance("small", 17)
    other, witness3 = generate_instance("small", 18)
    assert problem_to_dict(first) == problem_to_dict(second)
    assert schedule_to_dict(witness1) == schedule_to_dict(witness2)
    assert schedule_to_dict(witness1) != schedule_to_dict(witness3)
    assert first.metadata["seed"] != other.metadata["seed"]


def test_custom_calendar_resources_and_demand():
    problem, certificate = generate_instance("small", 7, {
        "groups": 1, "rooms": 4, "faculty": 4,
        "days": ["Mon", "Tue", "Wed"], "periods_per_day": 6,
        "lunch_periods": [3], "theory_offerings_per_group": 2,
        "theory_sessions": 2, "lab_offerings_per_group": 1,
        "max_weekly": 12, "max_daily": 4, "unavailability_rate": 0.2,
    })
    assert evaluate(problem, certificate).feasible
    assert len(problem.events) == 5
    assert len(problem.days) == 3
    assert sum(e.duration for e in problem.events) == 6
    assert problem.lunch_periods == (3,)


def test_teacher_qualification_alternatives_make_balance_decisional():
    problem, certificate = generate_instance("small", 0)
    original = evaluate(problem, certificate)
    found = False
    for ki, offering in enumerate(problem.offerings):
        for faculty in offering.eligible_faculty:
            teachers = list(certificate.teachers)
            teachers[ki] = faculty
            alternative = evaluate(problem, replace(certificate, teachers=tuple(teachers)))
            if alternative.feasible and alternative.objectives[2] != original.objectives[2]:
                found = True
                break
        if found:
            break
    assert found, "Workload balance must change under an actually feasible faculty reassignment"


@pytest.mark.parametrize("config", [
    {"rooms": 1}, {"groups": 0}, {"unavailability_rate": 1},
    {"unavailability_rate": -0.1}, {"lunch_periods": [8]},
    {"lunch_periods": [4, 4]}, {"days": ["Mon", "Mon"]},
    {"target_events": 1}, {"target_events": 1000},
    {"faculty": 1, "max_weekly": 1},
    {"theory_sessions": 3, "target_events": 40},
    {"periods_per_day": 1, "lunch_periods": []},
    {"unsupported_parameter": 42},
])
def test_invalid_or_obviously_impossible_generator_settings(config):
    with pytest.raises(ValueError):
        generate_instance("small", 0, config)


def test_unknown_preset_rejected():
    with pytest.raises(ValueError, match="Unknown size"):
        generate_instance("enormous", 0)


@pytest.mark.parametrize("theory_sessions", [True, False, 0, -1, 2.5, "2", None, [], float("nan"), float("inf")])
def test_theory_sessions_requires_a_positive_nonboolean_integer(theory_sessions):
    with pytest.raises(ValueError, match="theory_sessions must be a positive integer"):
        generate_instance("small", 0, {"theory_sessions": theory_sessions})


def test_theory_session_config_resolves_to_replayable_metadata():
    config = {"theory_sessions": 2}
    problem, certificate = generate_instance("small", 7, config)
    resolved = problem.metadata["config"]
    assert "theory_sessions" not in resolved
    assert resolved["target_events"] == 28
    assert config == {"theory_sessions": 2}
    replayed, replayed_certificate = generate_instance("small", 7, resolved)
    assert problem_to_dict(replayed) == problem_to_dict(problem)
    assert schedule_to_dict(replayed_certificate) == schedule_to_dict(certificate)


@pytest.mark.parametrize("size,seed", [("small", 10), ("medium", 20), ("large", 10)])
def test_default_presets_still_reproduce_saved_benchmark_data(size, seed):
    directory = Path(__file__).resolve().parents[1] / "data" / "benchmark"
    name = f"{size}_{seed}.json"
    problem, certificate = generate_instance(size, seed)
    assert json.dumps(problem_to_dict(problem), indent=2, allow_nan=False) + "\n" == (directory / name).read_text()
    assert json.dumps(schedule_to_dict(certificate), indent=2, allow_nan=False) + "\n" == (directory / "certificates" / name).read_text()
