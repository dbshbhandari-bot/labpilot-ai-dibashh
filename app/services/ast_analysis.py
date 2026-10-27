
import math
import statistics


def analyse_ast_replicates(measurements):
    """
    Calculate descriptive statistics for a set
    of comparable inhibition-zone measurements.

    measurements: list of zone diameters in mm
    """

    if not measurements:
        return None

    values = []

    for measurement in measurements:
        value = float(measurement)

        if not math.isfinite(value) or value < 0:
            raise ValueError(
                "Zone diameters must be finite "
                "and non-negative."
            )

        values.append(value)

    count = len(values)
    mean = statistics.mean(values)

    if count >= 2:
        standard_deviation = statistics.stdev(values)
    else:
        standard_deviation = None

    return {
        "count": count,
        "mean": round(mean, 2),
        "standard_deviation": (
            round(standard_deviation, 2)
            if standard_deviation is not None
            else None
        )
    }
