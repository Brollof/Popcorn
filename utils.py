def to_float(value, decimals=1):
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        return round(float(value), decimals)
    except:
        return 0.0