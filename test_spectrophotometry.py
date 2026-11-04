
import pytest

from app.routes.experiment_planner import analyse_calibration


# TEST 1: Verify correct scientific calculations
def test_calibration_known_result():

    concentrations = [0, 2, 4, 6, 8]
    absorbances = [0.02, 0.12, 0.22, 0.32, 0.42]
    unknown_absorbance = 0.27

    result = analyse_calibration(
        concentrations,
        absorbances,
        unknown_absorbance
    )

    assert result["slope"] == pytest.approx(0.05)
    assert result["intercept"] == pytest.approx(0.02)
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["unknown_concentration"] == pytest.approx(5.0)
    assert result["minimum_concentration"] == pytest.approx(0.0)
    assert result["maximum_concentration"] == pytest.approx(8.0)
    assert result["warnings"] == []


# TEST 2: Reject insufficient calibration standards
def test_calibration_rejects_insufficient_standards():

    concentrations = [0, 2]
    absorbances = [0.02, 0.12]
    unknown_absorbance = 0.07

    with pytest.raises(
        ValueError,
        match="At least three calibration standards are required"
    ):
        analyse_calibration(
            concentrations,
            absorbances,
            unknown_absorbance
        )


# TEST 3: Warn when concentration is outside calibration range
def test_calibration_extrapolation_warning():

    concentrations = [0, 2, 4, 6, 8]
    absorbances = [0.02, 0.12, 0.22, 0.32, 0.42]
    unknown_absorbance = 0.62

    result = analyse_calibration(
        concentrations,
        absorbances,
        unknown_absorbance
    )

    assert result["unknown_concentration"] == pytest.approx(12.0)

    assert (
        "Unknown concentration is above the calibration range."
        in result["warnings"]
    )


# TEST 4: Warn when calibration fit is poor
def test_calibration_poor_fit_warning():

    concentrations = [0, 2, 4, 6, 8]
    absorbances = [0.02, 0.30, 0.10, 0.45, 0.25]
    unknown_absorbance = 0.25

    result = analyse_calibration(
        concentrations,
        absorbances,
        unknown_absorbance
    )

    assert result["r_squared"] == pytest.approx(0.324921, abs=0.000001)

    assert any(
        "Calibration R-squared is below 0.95" in warning
        for warning in result["warnings"]
    )
