def format_currency_short(val):
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1_000_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000_000:,.2f}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}${abs_val / 1_000_000_000:,.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:,.1f}M"
    return f"{sign}${abs_val:,.0f}"


def format_abbrev_number(val):
    abs_val = abs(val)
    sign = "-" if val < 0 else ""

    def trim_num(v):
        return f"{v:,.3f}".rstrip("0").rstrip(".")

    if abs_val >= 1_000_000_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000_000_000)}T"
    if abs_val >= 1_000_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000_000)}B"
    if abs_val >= 1_000_000:
        return f"{sign}{trim_num(abs_val / 1_000_000)}M"
    return f"{val:,.0f}"


def parse_abbrev_number(text):
    raw = text.strip().upper().replace(",", "").replace("$", "")
    if not raw:
        raise ValueError("Empty numeric value")
    multiplier = 1.0
    suffix = raw[-1]
    if suffix in {"K", "M", "B", "T"}:
        raw = raw[:-1]
        multiplier = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[suffix]
    return float(raw) * multiplier
