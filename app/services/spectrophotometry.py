
import math


def analyse_calibration(concentrations, absorbances, unknown_absorbance):
    """
    Calculate a linear calibration curve and estimate
    the concentration of an unknown sample.

    Returns a dictionary containing the calculated results.
    """

    if len(concentrations) != len(absorbances):
        raise ValueError(
            "Concentration and absorbance lists must have equal lengths."
        )

    if len(concentrations) < 3:
        raise ValueError(
            "At least three calibration standards are required."
        )

    try:
        x = [float(value) for value in concentrations]
        y = [float(value) for value in absorbances]
        unknown = float(unknown_absorbance)
    except (TypeError, ValueError):
        raise ValueError("All measurements must be numeric.")

    if not all(math.isfinite(value) for value in x + y + [unknown]):
        raise ValueError("Measurements must be finite numbers.")

    if any(value < 0 for value in x):
        raise ValueError("Concentrations cannot be negative.")

    if len(set(x)) < 3:
        raise ValueError(
            "At least three distinct concentrations are required."
        )

    n = len(x)

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    # Calculate variation and covariance.
    sxx = sum((value - mean_x) ** 2 for value in x)

    sxy = sum(
        (x[i] - mean_x) * (y[i] - mean_y)
        for i in range(n)
    )

    if sxx == 0:
        raise ValueError(
            "Calibration concentrations must vary."
        )

    # Least-squares regression: absorbance = slope * concentration + intercept.
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    if not math.isfinite(slope) or not math.isfinite(intercept):
        raise ValueError("Calibration calculation failed.")

    if slope <= 0:
        raise ValueError(
            "Calibration slope must be positive for this analysis."
        )

    predicted_absorbances = [
        slope * concentration + intercept
        for concentration in x
    ]

    # Coefficient of determination (R-squared).
    ss_res = sum(
        (y[i] - predicted_absorbances[i]) ** 2
        for i in range(n)
    )

    ss_tot = sum(
        (value - mean_y) ** 2
        for value in y
    )

    if ss_tot == 0:
        raise ValueError(
            "Absorbance readings must vary."
        )

    r_squared = 1 - (ss_res / ss_tot)

    # Estimate concentration from the fitted line.
    unknown_concentration = (unknown - intercept) / slope

    if not all(math.isfinite(value) for value in [
        r_squared,
        unknown_concentration
    ]):
        raise ValueError("Calculated results are not finite.")

    minimum_concentration = min(x)
    maximum_concentration = max(x)

    warnings = []

    if unknown_concentration < minimum_concentration:
        warnings.append(
            "Unknown concentration is below the calibration range."
        )

    if unknown_concentration > maximum_concentration:
        warnings.append(
            "Unknown concentration is above the calibration range."
        )

    if r_squared < 0.95:
        warnings.append(
            "Calibration R-squared is below 0.95. "
            "Review the standards and assay requirements."
        )

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "unknown_concentration": unknown_concentration,
        "minimum_concentration": minimum_concentration,
        "maximum_concentration": maximum_concentration,
        "predicted_absorbances": predicted_absorbances,
        "warnings": warnings
    }
