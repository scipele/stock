#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import math
import xml.sax.saxutils as saxutils

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
COMBINED_REPORT = Path("/home/dev/stock/intr_buy/output/combined_report.csv")
DOWNLOAD_DIR = Path("/home/ts/Downloads")
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_SVG = OUTPUT_DIR / "stock_dei.svg"
OUTPUT_HTML = OUTPUT_DIR / "stock_dei.html"

SECTOR_NAMES = {
    1: "Basic Materials",
    2: "Communication Services",
    3: "Consumer Cyclical",
    4: "Consumer Defensive",
    5: "Energy",
    6: "Financial Services",
    7: "Healthcare",
    8: "Industrials",
    9: "Real Estate",
    10: "Technology",
    11: "Utilities",
}

BAND_ORDER = [
    (4, "Dow Jones", "#f28e2b"),
    (1, "S&P 500", "#2f6bff"),
    (8, "Russell 2000", "#2ca02c"),
]

TARGET_INDEXES = [band[0] for band in BAND_ORDER]
INDEX_LABELS = {band[0]: band[1] for band in BAND_ORDER}
INDEX_COLORS = {band[0]: band[2] for band in BAND_ORDER}
INDEX_PRIORITY = [band[0] for band in BAND_ORDER]

SECTOR_ORDER = [10, 5, 7, 6, 9, 8, 3, 4, 2, 1, 11]
ALL_SECTOR_IDS = SECTOR_ORDER


def find_latest_positions_file() -> Path:
    files = list(DOWNLOAD_DIR.glob("Fund-Positions-*.csv"))
    if not files:
        raise FileNotFoundError("No Fund-Positions-*.csv file found in /home/ts/Downloads")
    return max(files, key=lambda path: path.stat().st_mtime)


def clean_money(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)

    text = str(value).strip().replace("$", "").replace(",", "")
    if not text or text == "--":
        return 0.0
    return float(text)


def select_primary_index(bitmask: int) -> int | None:
    for index in INDEX_PRIORITY:
        if bitmask & index:
            return index
    return None


def load_positions() -> pd.DataFrame:
    filename = find_latest_positions_file()

    header_row = None
    with filename.open("r", encoding="utf-8", errors="ignore") as handle:
        for index, line in enumerate(handle):
            if line.lstrip().startswith('"Symbol"') or line.lstrip().startswith("Symbol,"):
                header_row = index
                break

    if header_row is None:
        raise RuntimeError(f"Could not find header row in {filename}")

    frame = pd.read_csv(filename, skiprows=header_row)
    frame.columns = [column.strip() for column in frame.columns]

    required = {"Symbol", "Asset Type", "Mkt Val (Market Value)"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"Positions file is missing required columns: {sorted(missing)}")

    frame = frame.dropna(subset=["Symbol"])
    frame = frame[frame["Symbol"].astype(str).str.strip().ne("")]
    frame = frame[frame["Symbol"].astype(str).str.upper().ne("POSITIONS TOTAL")]
    frame = frame[frame["Symbol"].astype(str).str.upper().ne("CASH & CASH INVESTMENTS")]
    frame = frame[frame["Asset Type"].astype(str).str.strip().eq("Equity")]

    positions = pd.DataFrame(
        {
            "Ticker": frame["Symbol"].astype(str).str.strip().str.upper(),
            "MarketValue": frame["Mkt Val (Market Value)"].apply(clean_money),
        }
    )

    return positions.groupby("Ticker", as_index=False).sum(numeric_only=True)


def load_owned_holdings(positions: pd.DataFrame) -> pd.DataFrame:
    report = pd.read_csv(COMBINED_REPORT)
    report.columns = [column.strip() for column in report.columns]

    required = {"Ticker", "Sector", "Index", "Owned"}
    missing = required - set(report.columns)
    if missing:
        raise RuntimeError(f"Combined report is missing required columns: {sorted(missing)}")

    report = report[report["Owned"].fillna("").astype(str).str.strip().eq("CP")]
    report["Index"] = pd.to_numeric(report["Index"], errors="coerce").fillna(0).astype(int)
    report["Sector"] = pd.to_numeric(report["Sector"], errors="coerce").fillna(0).astype(int)
    report["BandIndex"] = report["Index"].apply(select_primary_index)
    report = report.dropna(subset=["BandIndex"])
    report["BandIndex"] = report["BandIndex"].astype(int)

    merged = report.merge(positions, on="Ticker", how="inner")
    merged = merged[merged["MarketValue"] > 0].copy()

    merged["SectorName"] = merged["Sector"].map(SECTOR_NAMES).fillna("Unknown")
    merged["IndexLabel"] = merged["BandIndex"].map(INDEX_LABELS).fillna(merged["BandIndex"].astype(str))

    return merged


def polar_to_cartesian(cx: float, cy: float, radius: float, angle_rad: float) -> tuple[float, float]:
    return cx + radius * math.cos(angle_rad), cy + radius * math.sin(angle_rad)


def svg_arc_path(cx: float, cy: float, inner_radius: float, outer_radius: float, start_angle: float, end_angle: float) -> str:
    start_outer = polar_to_cartesian(cx, cy, outer_radius, start_angle)
    end_outer = polar_to_cartesian(cx, cy, outer_radius, end_angle)
    start_inner = polar_to_cartesian(cx, cy, inner_radius, end_angle)
    end_inner = polar_to_cartesian(cx, cy, inner_radius, start_angle)

    large_arc = 1 if end_angle - start_angle > math.pi else 0

    return (
        f"M {start_outer[0]:.2f} {start_outer[1]:.2f} "
        f"A {outer_radius:.2f} {outer_radius:.2f} 0 {large_arc} 1 {end_outer[0]:.2f} {end_outer[1]:.2f} "
        f"L {start_inner[0]:.2f} {start_inner[1]:.2f} "
        f"A {inner_radius:.2f} {inner_radius:.2f} 0 {large_arc} 0 {end_inner[0]:.2f} {end_inner[1]:.2f} Z"
    )


def ring_background_path(cx: float, cy: float, inner_radius: float, outer_radius: float) -> str:
    return svg_arc_path(cx, cy, inner_radius, outer_radius, -math.pi / 2, 3 * math.pi / 2)


def sector_groups(frame: pd.DataFrame) -> list[dict[str, object]]:
    grouped = []
    for sector_id in ALL_SECTOR_IDS:
        sector_frame = frame[frame["Sector"] == sector_id].copy()
        sector_total = float(sector_frame["MarketValue"].sum())

        values = {
            index: float(sector_frame[sector_frame["BandIndex"] == index]["MarketValue"].sum())
            for index in TARGET_INDEXES
        }

        grouped.append(
            {
                "sector_id": sector_id,
                "sector_name": SECTOR_NAMES.get(sector_id, f"Sector {sector_id}"),
                "total": sector_total,
                "values": values,
            }
        )

    return grouped


def build_svg(frame: pd.DataFrame) -> tuple[str, dict[int, float], dict[int, float], float]:
    sectors = sector_groups(frame)
    total_value = sum(item["total"] for item in sectors)
    if total_value <= 0:
        raise RuntimeError("No owned holdings were found after filtering")

    band_totals = {index: float(frame[frame["BandIndex"] == index]["MarketValue"].sum()) for index in TARGET_INDEXES}
    sector_totals = {item["sector_id"]: item["total"] for item in sectors}

    width = 1800
    height = 1400
    cx = width / 2
    cy = height / 2
    label_margin = 180.0
    sector_angle = 2 * math.pi / len(ALL_SECTOR_IDS)

    center_hole_radius = 92.0
    max_ring_radius = 430.0
    ring_gap = 26.0
    chart_area = math.pi * (max_ring_radius ** 2 - center_hole_radius ** 2)

    ring_geometries = []
    cumulative_share = 0.0
    previous_outer = center_hole_radius
    for index, label, color in BAND_ORDER:
        band_total = float(band_totals.get(index, 0.0))
        band_share = band_total / total_value if total_value > 0 else 0.0
        computed_inner = math.sqrt(center_hole_radius ** 2 + cumulative_share * (max_ring_radius ** 2 - center_hole_radius ** 2))
        cumulative_share += band_share
        computed_outer = math.sqrt(center_hole_radius ** 2 + cumulative_share * (max_ring_radius ** 2 - center_hole_radius ** 2))

        ring_inner_radius = max(computed_inner, previous_outer + ring_gap)
        ring_outer_radius = max(computed_outer, ring_inner_radius)

        ring_geometries.append(
            {
                "index": index,
                "label": label,
                "color": color,
                "inner": ring_inner_radius,
                "outer": ring_outer_radius,
                "separator_inner": previous_outer,
                "separator_outer": ring_inner_radius,
            }
        )
        previous_outer = ring_outer_radius

    outer_radius = ring_geometries[-1]["outer"]

    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        "  <mask id=\"outer-bg-mask\">",
        f"    <rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" fill=\"white\" />",
        f"    <circle cx=\"{cx}\" cy=\"{cy}\" r=\"{outer_radius + 12.0:.2f}\" fill=\"black\" />",
        "  </mask>",
        "</defs>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#121212" mask="url(#outer-bg-mask)"/>',
    ]

    for ring in ring_geometries:
        ring_center_radius = (ring["inner"] + ring["outer"]) / 2
        ring_thickness = ring["outer"] - ring["inner"]
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{ring_center_radius:.2f}" fill="none" stroke="#ffffff" '
            f'stroke-width="{ring_thickness:.2f}" stroke-opacity="0.0"/>'
        )

    # This is the inner circle
    svg_parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{ring_geometries[0]["inner"]:.2f}" fill="#575353" opacity="0.9"/>' #try #798694, was #edf1f5
    )

    start_angle = -math.pi / 2
    sector_geometry = []
    for sector_index, sector in enumerate(sectors):
        sector_start = start_angle + sector_index * sector_angle
        sector_end = sector_start + sector_angle
        sector_mid = (sector_start + sector_end) / 2
        sector_geometry.append((sector, sector_start, sector_end, sector_mid))

    for _, sector_start, sector_end, _ in sector_geometry:
        svg_parts.append(
            f'<path d="{svg_arc_path(cx, cy, ring_geometries[0]["inner"], outer_radius, sector_start, sector_end)}" '
            'fill="none" stroke="#d9e0e8" stroke-width="1.0" opacity="0.8"/>'
        )

    for ring in ring_geometries:
        index = ring["index"]
        ring_inner = float(ring["inner"])
        ring_outer = float(ring["outer"])
        ring_total = float(band_totals.get(index, 0.0))

        separator_inner = float(ring.get("separator_inner", ring_inner))
        separator_outer = float(ring.get("separator_outer", ring_outer))

        if separator_outer > separator_inner:
            svg_parts.append(
                f'<path d="{ring_background_path(cx, cy, separator_inner, separator_outer)}" '
                'fill="#8a8686" fill-opacity="1.0" stroke="#374151" stroke-width="2.0"/>'  # try
            )

        svg_parts.append(
            f'<path d="{ring_background_path(cx, cy, ring_inner, ring_outer)}" fill="#dfe7ef" fill-opacity="0.9" stroke="#d1d5db" stroke-width="1.2"/>'
        )

        for sector, sector_start, sector_end, _ in sector_geometry:
            sector_slice = svg_arc_path(cx, cy, ring_inner, ring_outer, sector_start, sector_end)
            svg_parts.append(
                f'<path d="{sector_slice}" fill="#ffffff" fill-opacity="0.95" stroke="#4b5563" stroke-width="0.8"/>'
            )

            value = float(sector["values"].get(index, 0.0))
            if value <= 0 or ring_total <= 0:
                continue

            fill_fraction = value / ring_total
            fill_outer = math.sqrt(ring_inner ** 2 + (ring_outer ** 2 - ring_inner ** 2) * fill_fraction)
            path = svg_arc_path(cx, cy, ring_inner, fill_outer, sector_start, sector_end)
            svg_parts.append(
                f'<path d="{path}" fill="{ring["color"]}" fill-opacity="1.0" stroke="#4b5563" stroke-width="0.8"/>'
            )

    svg_parts.append(
        f'<text x="{cx}" y="44" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" '
        'font-size="28" font-weight="700" fill="#FF79C6">Owned market value</text>'
    )

    for sector, _, _, sector_mid in sector_geometry:
        label_x_side = cx + outer_radius + label_margin if math.cos(sector_mid) >= 0 else cx - outer_radius - label_margin
        label_anchor = "start" if label_x_side > cx else "end"
        elbow_x = cx + math.cos(sector_mid) * (outer_radius + 22)
        elbow_y = cy + math.sin(sector_mid) * (outer_radius + 22)
        leader_end_x = label_x_side - 14 if label_anchor == "start" else label_x_side + 14

        svg_parts.append(
            f'<polyline points="{elbow_x:.2f},{elbow_y:.2f} {leader_end_x:.2f},{elbow_y:.2f}" '
            'fill="none" stroke="#FDFEFE" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        svg_parts.append(f'<circle cx="{elbow_x:.2f}" cy="{elbow_y:.2f}" r="2.5" fill="#FDFEFE"/>') 
        svg_parts.append(
            f'<text x="{label_x_side:.2f}" y="{elbow_y:.2f}" text-anchor="{label_anchor}" '
            'dominant-baseline="middle" font-family="DejaVu Sans, Arial, sans-serif" '
            'font-size="16" font-weight="700" fill="#FF79C6">'
            f'{saxutils.escape(sector["sector_name"])}'
            "</text>"
        )

    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="#2b3037"/>')
    svg_parts.append(
        f'<text x="{cx}" y="1315" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" '
        'font-size="13" fill="#FDFEFE">Overlaps display in Dow first, then S&amp;P 500, then Russell 2000</text>'
    )

    legend_x = 70
    legend_y = 70
    svg_parts.append(f'<g font-family="DejaVu Sans, Arial, sans-serif" font-size="18" fill="#FDFEFE">')
    svg_parts.append(f'<text x="{legend_x}" y="{legend_y}" font-size="24" font-weight="700">Bands</text>')
    offset_y = 38
    for index in TARGET_INDEXES:
        color = INDEX_COLORS[index]
        svg_parts.append(
            f'<rect x="{legend_x}" y="{legend_y + offset_y - 16}" width="22" height="22" rx="4" fill="{color}" fill-opacity="0.72" stroke="#ffffff" stroke-width="1.5"/>'
        )
        svg_parts.append(
            f'<text x="{legend_x + 34}" y="{legend_y + offset_y}" dominant-baseline="middle">{saxutils.escape(INDEX_LABELS[index])}</text>'
        )
        offset_y += 32
    svg_parts.append("</g>")

    svg_parts.append("</svg>")
    return "\n".join(svg_parts), band_totals, sector_totals, total_value


def write_outputs(svg_text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_SVG.write_text(svg_text, encoding="utf-8")
    OUTPUT_HTML.write_text(
        "<!doctype html>\n<html><head><meta charset='utf-8'><title>Owned Sector Map</title>"
        "<style>body{margin:0;background:#121212;}svg{display:block;width:100vw;height:100vh;}</style>"
        "</head><body>" + svg_text + "</body></html>",
        encoding="utf-8",
    )


def main() -> int:
    positions = load_positions()
    holdings = load_owned_holdings(positions)
    svg_text, band_totals, sector_totals, total_value = build_svg(holdings)
    write_outputs(svg_text)

    print(f"Latest positions file: {find_latest_positions_file().name}")
    print(f"Combined report: {COMBINED_REPORT}")
    print(f"Output SVG: {OUTPUT_SVG}")
    print(f"Output HTML: {OUTPUT_HTML}")
    print(f"Total owned market value: ${total_value:,.2f}")
    print("Index totals:")
    for index in TARGET_INDEXES:
        print(f"  {INDEX_LABELS[index]:<13} ${band_totals[index]:,.2f}")
    print("Sector totals:")
    for sector_id in SECTOR_ORDER:
        total = sector_totals.get(sector_id)
        if total:
            print(f"  {SECTOR_NAMES[sector_id]:<22} ${total:,.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())