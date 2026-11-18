"""MCDM input validity and exact zero-weight boundary regressions."""
from __future__ import annotations

import math

import pytest

from timetable.mcdm import ahp_from_judgements, ahp_weights, recommend, topsis, weight_sensitivity


@pytest.mark.parametrize("weights", [(-1, 1, 1), (math.nan, 1, 1), (math.inf, 1, 1), (0, 0, 0), (1, 1)])
@pytest.mark.parametrize("objectives", [[], [(0.0, 1.0, 2.0)]])
def test_invalid_weights_rejected_even_for_empty_front(objectives, weights):
    for operation in (topsis, recommend, weight_sensitivity):
        with pytest.raises(ValueError, match="weights"):
            operation(objectives, weights)


@pytest.mark.parametrize("objectives", [[(1, 2)], [(1, 2, 3, 4)], [(1, math.nan, 3)], [(math.inf, 2, 3)]])
def test_topsis_rejects_malformed_or_nonfinite_alternatives(objectives):
    with pytest.raises(ValueError, match="objective"):
        topsis(objectives)


def test_topsis_normalization_handles_large_finite_values_and_weights():
    ordinary = topsis([(1.0, 1.0, 1.0), (1.5, 0.5, 1.0)], (1, 1, 1))
    scaled = topsis([(1e308, 1e308, 1e308), (1.5e308, 0.5e308, 1e308)], (1e308, 1e308, 1e308))
    assert [r.solution_index for r in scaled] == [r.solution_index for r in ordinary]
    assert [r.score for r in scaled] == [r.score for r in ordinary]


def test_sensitivity_uses_the_same_zero_weight_ties_as_topsis():
    # On room weight zero, both alternatives tie and input order wins.
    objectives = [(1.0, 100.0, 0.0), (1.0, 0.0, 0.0)]
    result = weight_sensitivity(objectives, (1, 0, 0), divisions=2, sweep_steps=2)
    assert result["base_choice"] == topsis(objectives, (1, 0, 0))[0].solution_index == 0
    assert {p["index"]: p["share"] for p in result["weight_space"]} == {0: 0.5, 1: 0.5}
    assert result["sweeps"][0]["segments"][-1]["index"] == 0


@pytest.mark.parametrize("kwargs", [{"divisions": 2.5}, {"sweep_steps": 2.5}, {"divisions": True}, {"sweep_steps": 1}])
def test_sensitivity_requires_integer_grid_sizes(kwargs):
    with pytest.raises(ValueError, match="integers"):
        weight_sensitivity([(0, 0, 0)], **kwargs)


@pytest.mark.parametrize("judgement", [0.0, -1.0, math.inf, math.nan])
def test_ahp_judgements_are_positive_and_finite(judgement):
    with pytest.raises(ValueError, match="positive and finite"):
        ahp_from_judgements(judgement, 1, 1)


def test_recommend_rejects_wrong_ahp_arity_as_value_error():
    with pytest.raises(ValueError, match="three pairwise"):
        recommend([(0, 0, 0)], ahp=[1, 1])


def test_ahp_large_finite_reciprocal_matrix_does_not_overflow_iteration():
    # Each row has two large judgements. The old unscaled normalization
    # overflowed its sum and subsequently divided by zero.
    n = 5
    matrix = [[1.0 if i == j else 1e308 if (j - i) % n <= 2 else 1e-308
               for j in range(n)] for i in range(n)]
    with pytest.raises(ValueError, match="ill-conditioned"):
        # Its true eigenvalue itself is outside finite float range; reject it
        # explicitly instead of returning NaN weights or a misleading CR.
        ahp_weights(matrix)


def test_empty_recommendation_remains_well_defined():
    result = recommend([], weights=(1e308, 1e308, 1e308))
    assert result["recommended"] is None
    assert result["ranking"] == []
    assert result["weights"] == pytest.approx([1 / 3] * 3)
