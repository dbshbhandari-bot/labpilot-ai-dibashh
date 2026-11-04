
import math
import pytest

from app.services.serial_dilution import (
    calculate_cfu,
    analyse_cfu
)


# TEST 1: Verify a known CFU calculation
def test_cfu_known_result():
    result = calculate_cfu(
        colonies=150.0,
        dilution=0.0001,
        volume_ml=0.1
    )

    assert result == pytest.approx(15000000.0)


# TEST 2: Reject negative colony counts
def test_cfu_negative_colonies():
    result = calculate_cfu(-5.0, 0.001, 0.1)

    assert result is None


# TEST 3: Reject fractional colony counts
def test_cfu_fractional_colonies():
    result = calculate_cfu(25.5, 0.001, 0.1)

    assert result is None


# TEST 4: Reject zero dilution
def test_cfu_zero_dilution():
    result = calculate_cfu(100.0, 0, 0.1)

    assert result is None


# TEST 5: Reject dilution greater than one
def test_cfu_invalid_dilution():
    result = calculate_cfu(100.0, 2.0, 0.1)

    assert result is None


# TEST 6: Reject zero plated volume
def test_cfu_zero_volume():
    result = calculate_cfu(100.0, 0.001, 0)

    assert result is None


# TEST 7: Reject non-finite values
@pytest.mark.parametrize(
    "invalid_value",
    [math.nan, math.inf, -math.inf]
)
def test_cfu_non_finite_colonies(invalid_value):
    result = calculate_cfu(
        invalid_value,
        0.001,
        0.1
    )

    assert result is None


# TEST 8: Verify zero colony calculation
def test_cfu_zero_colonies():
    result = calculate_cfu(0.0, 0.001, 0.1)

    assert result == pytest.approx(0.0)


# TEST 9: Check low colony warning
def test_cfu_low_count_warning():
    analysis = analyse_cfu(
        colonies=15.0,
        dilution=0.001,
        volume_ml=0.1,
        cfu_per_ml=150000.0
    )

    assert any(
        "relatively low" in message
        for message in analysis
    )


# TEST 10: Check commonly countable range
def test_cfu_countable_range():
    analysis = analyse_cfu(
        colonies=150.0,
        dilution=0.001,
        volume_ml=0.1,
        cfu_per_ml=1500000.0
    )

    assert any(
        "commonly used countable" in message
        for message in analysis
    )


# TEST 11: Check high colony warning
def test_cfu_high_count_warning():
    analysis = analyse_cfu(
        colonies=450.0,
        dilution=0.001,
        volume_ml=0.1,
        cfu_per_ml=4500000.0
    )

    assert any(
        "interpreted cautiously" in message
        for message in analysis
    )


# TEST 12: Check zero colony explanation
def test_cfu_zero_count_explanation():
    analysis = analyse_cfu(
        colonies=0.0,
        dilution=0.001,
        volume_ml=0.1,
        cfu_per_ml=0.0
    )

    assert any(
        "No colonies were recorded" in message
        for message in analysis
    )
