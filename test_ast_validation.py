
from app.services.ast_analysis  import analyse_ast_replicates


def test_ast_mean_and_standard_deviation():

    # Three inhibition-zone measurements in millimetres
    measurements = [10.0, 20.0, 30.0]

    # Run the actual LabPilot AI calculation
    result = analyse_ast_replicates(measurements)

    # Check the scientific results
    assert result["count"] == 3
    assert result["mean"] == 20.0
    assert result["standard_deviation"] == 10.0

import pytest

def test_ast_rejects_negative_zone_diameter():
        # Negative inhibition-zone measurements are invalid
        measurements = [10.0, -5.0, 20.0]

        # LabPilot AI must reject these measurements
        with pytest.raises(ValueError):
            analyse_ast_replicates(measurements)



def test_ast_handles_empty_measurements():

    # Researcher has not entered any measurements
    measurements = []

    # Run the actual LabPilot AI calculation
    result = analyse_ast_replicates(measurements)

    # No measurements means no statistical result
    assert result is None

def test_ast_rejects_nan_and_infinity():

    invalid_values = [
        float("nan"),
        float("inf"),
        float("-inf")
    ]

    for invalid_value in invalid_values:

        measurements = [10.0, invalid_value, 20.0]

        with pytest.raises(ValueError):
            analyse_ast_replicates(measurements)
