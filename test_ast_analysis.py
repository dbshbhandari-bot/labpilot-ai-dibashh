
import math
import pytest

from app.services.ast_analysis import analyse_ast_replicates


# TEST 1: Verify mean and standard deviation
def test_ast_known_measurements():

    result = analyse_ast_replicates([18, 20, 22])

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(20.0)
    assert result["standard_deviation"] == pytest.approx(2.0)


# TEST 2: Verify identical replicate measurements
def test_ast_identical_measurements():

    result = analyse_ast_replicates([20, 20, 20])

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(20.0)
    assert result["standard_deviation"] == pytest.approx(0.0)


# TEST 3: Handle a single measurement
def test_ast_single_measurement():

    result = analyse_ast_replicates([18])

    assert result["count"] == 1
    assert result["mean"] == pytest.approx(18.0)
    assert result["standard_deviation"] is None


# TEST 4: Handle an empty list
def test_ast_empty_measurements():

    result = analyse_ast_replicates([])

    assert result is None


# TEST 5: Reject negative zone diameters
def test_ast_negative_measurement():

    with pytest.raises(ValueError):
        analyse_ast_replicates([18, -2, 20])


# TEST 6: Reject non-finite measurements
@pytest.mark.parametrize(
    "invalid_value",
    [math.nan, math.inf, -math.inf]
)
def test_ast_non_finite_measurement(invalid_value):

    with pytest.raises(ValueError):
        analyse_ast_replicates([18, invalid_value, 20])


# TEST 7: Verify decimal measurements
def test_ast_decimal_measurements():

    result = analyse_ast_replicates([18.5, 19.5, 20.5])

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(19.5)
    assert result["standard_deviation"] == pytest.approx(1.0)


# TEST 8: Verify rounding behaviour
def test_ast_rounding():

    result = analyse_ast_replicates([10, 11, 12, 14])

    assert result["mean"] == pytest.approx(11.75)
    assert result["standard_deviation"] == pytest.approx(1.71)


# TEST 9: Accept zero as a valid zone measurement
def test_ast_zero_measurement():

    result = analyse_ast_replicates([0, 0, 0])

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(0.0)
    assert result["standard_deviation"] == pytest.approx(0.0)


# TEST 10: Accept numeric strings
def test_ast_numeric_strings():

    result = analyse_ast_replicates(["18", "20", "22"])

    assert result["count"] == 3
    assert result["mean"] == pytest.approx(20.0)
    assert result["standard_deviation"] == pytest.approx(2.0)


# TEST 11: Reject non-numeric text
def test_ast_invalid_text():

    with pytest.raises(ValueError):
        analyse_ast_replicates(["18", "invalid", "22"])
