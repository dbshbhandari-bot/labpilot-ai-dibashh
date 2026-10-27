
import math


def calculate_cfu(colonies, dilution, volume_ml):

    values = (colonies, dilution, volume_ml)

    if not all(math.isfinite(value) for value in values):
        return None

    if colonies < 0:
        return None

    if not colonies.is_integer():
        return None

    if dilution <= 0 or dilution > 1:
        return None

    if volume_ml <= 0:
        return None

    result = colonies / (dilution * volume_ml)

    if not math.isfinite(result):
        return None

    return result

def analyse_cfu(colonies, dilution, volume_ml, cfu_per_ml):

    analysis = []

    analysis.append(
        f"The estimated concentration of the original sample is "
        f"{cfu_per_ml:.2e} CFU/mL."
    )

    if colonies == 0:
        analysis.append(
            "No colonies were recorded on the plate."
        )

    elif colonies < 30:
        analysis.append(
            "The colony count is relatively low, so the calculated "
            "estimate may be more sensitive to counting variation."
        )

    elif colonies <= 300:
        analysis.append(
            "The colony count falls within a commonly used countable "
            "range for plate-based colony estimation."
        )

    else:
        analysis.append(
            "The colony count is above the commonly used countable "
            "range, so the result should be interpreted cautiously."
        )

    analysis.append(
        f"The calculation used a dilution of {dilution:g} "
        f"and a plated volume of {volume_ml:g} mL."
    )

    return analysis