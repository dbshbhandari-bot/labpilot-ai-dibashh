def calculate_cfu(colonies, dilution, volume_ml):

    if colonies < 0:
        return None

    if dilution <= 0:
        return None

    if volume_ml <= 0:
        return None

    cfu_per_ml = colonies / (dilution * volume_ml)

    return cfu_per_ml
