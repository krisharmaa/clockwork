"""Tests for newly implemented optimization techniques: MOEA/D, AMOSA, TOPSIS MCDM, and Epsilon-Constraint CP-SAT."""
from __future__ import annotations

import pytest

from timetable.amosa import amosa
from timetable.evaluation import evaluate
from timetable.examples import conflict_instance
from timetable.exact import cp_sat, epsilon_constraint_cp_sat
from timetable.generation import generate_instance
from timetable.mcdm import analyze_stakeholder_profiles, topsis
from timetable.moead import generate_simplex_weights, moead, tchebycheff, weighted_sum


def test_weight_generation():
    weights = generate_simplex_weights(12, dim=3, seed=0)
    assert len(weights) == 12
    for w in weights:
        assert len(w) == 3
        assert pytest.approx(sum(w), rel=1e-4) == 1.0
        assert all(coord > 0 for coord in w)


def test_moead_runs_and_evaluates():
    problem, _ = generate_instance("small", 9002)
    calls = []

    def observer(p, s):
        calls.append(s)
        return evaluate(p, s)

    result = moead(problem, seed=9002, population_size=6, max_evaluations=36, evaluator=observer)
    assert result.evaluations == len(calls) == 36
    assert result.metadata["evaluated_feasible"] == 36
    assert len(result.archive) >= 1
    assert all(evaluate(problem, s).feasible for s in result.archive)


def test_amosa_runs_and_evaluates():
    problem, _ = generate_instance("small", 9002)
    calls = []

    def observer(p, s):
        calls.append(s)
        return evaluate(p, s)

    result = amosa(problem, seed=9002, population_size=6, max_evaluations=36, evaluator=observer)
    assert result.evaluations == len(calls) == 36
    assert len(result.archive) >= 1
    assert all(evaluate(problem, s).feasible for s in result.archive)


def test_topsis_mcdm_ranking():
    # 2 extreme alternatives:
    # Sol 0: Perfect gaps (0.0), poor room fit (1.0), equal workload (0.1)
    # Sol 1: Poor gaps (10.0), near-perfect room fit (0.01), equal workload (0.1)
    candidates = [
        (0.0, 1.0, 0.1),
        (10.0, 0.01, 0.1),
    ]
    # Under student-first profile (80% gaps), Sol 0 must be top
    student_ranking = topsis(candidates, weights=(0.8, 0.1, 0.1))
    assert student_ranking[0].solution_index == 0

    # Under admin room-fit profile (80% room), Sol 1 must be top
    room_ranking = topsis(candidates, weights=(0.1, 0.8, 0.1))
    assert room_ranking[0].solution_index == 1

    # Analysis across stakeholder profiles
    analysis = analyze_stakeholder_profiles(candidates)
    assert "balanced" in analysis
    assert "student_first" in analysis
    assert "admin_room_fit" in analysis
    assert "faculty_fairness" in analysis


def test_epsilon_constraint_cp_sat_micro():
    problem = conflict_instance("room")
    res = epsilon_constraint_cp_sat(problem, time_limit_per_step=3.0, steps=3)
    assert res.evaluated_steps == 3
    assert len(res.archive) >= 1
    assert all(evaluate(problem, s).feasible for s in res.archive)


@pytest.mark.parametrize("method,kwargs", [
    (moead, {"neighborhood_size": 0}), (moead, {"max_replacements": 0}),
    (moead, {"faculty_every": 0}), (moead, {"faculty_nodes": 0}),
    (amosa, {"population_size": 0}), (amosa, {"faculty_every": 0}),
    (amosa, {"faculty_nodes": 0}), (amosa, {"alpha": 1.0}),
    (amosa, {"alpha": float("nan")}), (amosa, {"t_max": float("inf")}),
])
def test_search_rejects_parameters_that_break_search(method, kwargs):
    with pytest.raises(ValueError):
        method(conflict_instance("room"), max_evaluations=10, **kwargs)


def test_moead_distinguishes_plain_and_augmented_scalarization(monkeypatch):
    import timetable.moead as module

    original = module.tchebycheff
    rhos = []

    def observe(*args, **kwargs):
        rhos.append(kwargs["rho"])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "tchebycheff", observe)
    problem = conflict_instance("room")
    for mode, expected in (("tchebycheff", 0.0), ("augmented_tchebycheff", 1e-3)):
        rhos.clear()
        moead(problem, scalarization=mode, population_size=4, max_evaluations=8, use_faculty_search=False)
        assert rhos and set(rhos) == {expected}


def test_scalarization_matches_formulas_and_rejects_silent_dimension_loss():
    assert tchebycheff((1, 3, 2), (0.5, 0.25, 0.25), (2, 1, 0), (1, 2, 2), rho=0) == 0.5
    assert weighted_sum((1, 3, 2), (0.5, 0.25, 0.25), (1, 2, 2)) == 1.125
    for func in (weighted_sum, lambda f, w, s: tchebycheff(f, w, (0, 0, 0), s)):
        with pytest.raises(ValueError):
            func((1, 2, 3), (1, 1), (1, 1, 1))
        with pytest.raises(ValueError):
            func((1, 2, 3), (1, 1, 1), (1, 0, 1))


def test_amosa_alpha_controls_geometric_temperature():
    problem = conflict_instance("room")
    results = [amosa(problem, population_size=2, max_evaluations=20, use_faculty_search=False,
                     t_max=1.0, t_min=1e-12, alpha=alpha) for alpha in (0.5, 0.9)]
    assert all(result.evaluations == 20 for result in results)
    assert 0 < results[0].metadata["temperature"] < results[1].metadata["temperature"] < 1


@pytest.mark.parametrize("method", [moead, amosa])
def test_new_searches_are_deterministic_nondominated_and_handle_infeasible_models(method):
    from dataclasses import replace
    from timetable.metrics import dominates

    problem = conflict_instance("room")
    kwargs = {"seed": 4, "population_size": 4, "max_evaluations": 20, "use_faculty_search": False}
    a, b = method(problem, **kwargs), method(problem, **kwargs)
    assert a.archive == b.archive and a.population == b.population
    objectives = [evaluate(problem, s).objectives for s in a.archive]
    assert len(objectives) == len(set(objectives))
    assert not any(dominates(x, y) for x in objectives for y in objectives)
    impossible = replace(problem, rooms=())
    failed = method(impossible, **kwargs)
    assert not failed.archive and failed.evaluations <= kwargs["max_evaluations"]


@pytest.mark.parametrize("method", [moead, amosa])
def test_new_searches_handle_a_well_formed_empty_problem(method):
    from timetable.model import Problem, Schedule

    problem = Problem("empty", ("Mon",), 3, (), (), (), (), ())
    result = method(problem, population_size=2, max_evaluations=10, use_faculty_search=False)
    assert result.evaluations == 10 and result.archive == [Schedule((), ())]
