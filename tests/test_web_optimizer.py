"""The website run reports measured comparison data only: nothing is estimated for algorithms that did not run."""
import api.optimizer as optimizer
from api.bridge import demo_problem
from api.optimizer import RunConfig, run_optimizer

COMPARED = ("moead", "amosa", "nsga2")


def test_run_without_comparison_reports_only_the_final_method():
    stats = run_optimizer(demo_problem(), RunConfig(budget=40, search_seconds=None, compare_baseline=False), save=False)["stats"]
    assert [a["id"] for a in stats["algorithmComparison"]] == ["memetic"]
    assert list(stats["multiConvergence"]) == ["memetic"]
    assert not any(f"{key}Front" in stats for key in COMPARED)
    assert stats["baselineMethod"] is None and stats["baselineFront"] == []


def test_normal_run_is_final_method_plus_greedy_only():
    """MOEA/D, AMOSA and standard NSGA-II belong to the optional advanced benchmark, not to a normal run."""
    result = run_optimizer(demo_problem(), RunConfig(budget=40, search_seconds=None), save=False)
    stats = result["stats"]
    assert result["params"]["advancedBenchmark"] is False and stats["advancedBenchmark"] is False
    assert [a["id"] for a in stats["algorithmComparison"]] == ["memetic", "greedy"]
    assert set(stats["multiConvergence"]) == {"memetic", "greedy"}
    assert not any(f"{key}Front" in stats for key in COMPARED)
    assert stats["baselineEvaluations"] == stats["evaluations"]


def test_comparison_curves_are_measured_history_points():
    result = run_optimizer(demo_problem(), RunConfig(budget=60, search_seconds=None, advanced_benchmark=True), save=False)
    assert result["params"]["advancedBenchmark"] is True
    stats = result["stats"]
    rows = {a["id"]: a for a in stats["algorithmComparison"]}
    assert set(rows) == {"memetic", "greedy", *COMPARED}
    for key, row in rows.items():
        assert row["status"] in {"ok", "no_feasible"}
        curve = stats["multiConvergence"][key]
        evaluations = [p["evaluations"] for p in curve]
        assert evaluations == sorted(evaluations) and 0 < evaluations[0] and evaluations[-1] <= stats["evaluations"]
        if key != "greedy":  # greedy records every evaluation and is thinned to about 30 samples
            assert abs(curve[-1]["hypervolume"] - row["hv"]) < 1e-3  # the curve ends at the reported hypervolume
        front = stats["baselineFront" if key == "greedy" else f"{key}Front"]
        assert len(front) == row["frontSize"] and (row["status"] == "ok") == bool(front)
        if row["status"] == "no_feasible":
            assert row["hv"] == 0 and all(p["hypervolume"] == 0 for p in curve)


def test_failed_comparison_is_reported_not_replaced(monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("deliberate test failure")

    monkeypatch.setattr(optimizer, "moead", broken)
    stats = run_optimizer(demo_problem(), RunConfig(budget=40, search_seconds=None, advanced_benchmark=True), save=False)["stats"]
    row = next(a for a in stats["algorithmComparison"] if a["id"] == "moead")
    assert row["status"] == "failed" and row["hv"] is None and row["frontSize"] == 0
    assert "deliberate test failure" in row["error"]
    assert "moead" not in stats["multiConvergence"] and "moeadFront" not in stats


def test_website_uses_exact_fronts_and_preserves_native_measurements(monkeypatch, tmp_path):
    """The saved equal-variance ULP counterexample must not become two Pareto options."""
    from hashlib import sha256
    import json
    from pathlib import Path
    from timetable.model import problem_from_dict, schedule_from_dict, schedule_to_dict
    from timetable.nsga2 import SearchResult

    root = Path(__file__).resolve().parents[1]
    problem = problem_from_dict(json.loads((root / "data/enhancement_validation/large_1010.json").read_text()))
    raw = json.loads((root / "results/enhancement_validation/runs/large_1010_evaluations_memetic_0.json").read_text())
    schedules = [schedule_from_dict(raw["archive"][i]) for i in (8, 9)]
    search = SearchResult(schedules, [], 2, 0.01, best_schedule=schedules[0], population=schedules)
    for name in ("memetic_nsga2", "greedy_search", "moead", "amosa", "nsga2"):
        monkeypatch.setattr(optimizer, name, lambda *_args, **_kwargs: search)
    monkeypatch.setenv("CLOCKWORK_RUNS_DIR", str(tmp_path))
    result = run_optimizer(problem, RunConfig(budget=40, search_seconds=None, advanced_benchmark=True), run_id="precision")
    stats = result["stats"]
    assert stats["frontSize"] == stats["baselineFrontSize"] == 1
    assert stats["rawFrontSize"] == 2
    assert all(row["frontSize"] == 1 for row in stats["algorithmComparison"])
    assert len([s for s in result["solutions"] if s["onFront"]]) == 1
    assert result["solutions"][0]["objectives"]["f3"] == result["solutions"][1]["objectives"]["f3"]
    assert result["solutions"][0]["objectives"]["f2"] < result["solutions"][1]["objectives"]["f2"]
    assert not result["solutions"][1]["onFront"]
    saved = tmp_path / "precision"
    native = json.loads((saved / "run.json").read_text())
    exact = json.loads((saved / "exact_front.json").read_text())
    assert len(native["archive"]) == 2 and len(exact["archive"]) == 1
    assert exact["run_sha256"] == sha256((saved / "run.json").read_bytes()).hexdigest()
    assert exact["archive"][0] == json.loads(json.dumps(schedule_to_dict(schedules[0])))


def test_invalid_comparison_archive_is_reported_as_failure(monkeypatch):
    from dataclasses import replace
    from timetable.greedy import greedy
    from timetable.nsga2 import SearchResult
    problem = demo_problem()
    schedule = greedy(problem, seed=1)
    broken = replace(schedule, placements=(None,) + schedule.placements[1:])
    monkeypatch.setattr(optimizer, "moead", lambda *_args, **_kwargs: SearchResult([broken], [], 1, 0.01))
    stats = run_optimizer(problem, RunConfig(budget=40, search_seconds=None, advanced_benchmark=True), save=False)["stats"]
    row = next(r for r in stats["algorithmComparison"] if r["id"] == "moead")
    assert row["status"] == "failed" and row["hv"] is None and row["frontSize"] == 0
    assert "moeadFront" not in stats
