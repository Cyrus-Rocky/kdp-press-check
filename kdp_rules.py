"""KDP paperback interior rules, sourced from Amazon KDP's published print
specifications (trim sizes, margins, bleed, fonts, image resolution).
All checks here are deterministic — no AI involved.
"""

POINTS_PER_INCH = 72
TOLERANCE_IN = 0.06  # allow small measurement/rounding slack

# Common KDP paperback trim sizes (width x height, inches)
TRIM_SIZES_IN = [
    (5, 8), (5.06, 7.81), (5.25, 8), (5.5, 8.5), (6, 9),
    (6.14, 9.21), (6.69, 9.61), (7, 10), (7.44, 9.69),
    (7.5, 9.25), (8, 10), (8.25, 6), (8.25, 8.25),
    (8.5, 8.5), (8.5, 11), (8.27, 11.69),
]

MIN_IMAGE_DPI = 300
RECOMMENDED_IMAGE_DPI = 300


def inside_margin_in(page_count: int) -> float:
    """KDP's minimum inside (gutter-side) margin, scaled by page count."""
    if page_count <= 150:
        return 0.375
    if page_count <= 300:
        return 0.5
    if page_count <= 500:
        return 0.625
    if page_count <= 700:
        return 0.75
    return 0.875


MIN_OUTSIDE_TOP_BOTTOM_MARGIN_IN = 0.25
MIN_BLEED_OUTER_IN = 0.125
MIN_BLEED_BOTTOM_IN = 0.25

# KDP bleed spec: a full-bleed page is the plain trim size plus 0.125" on the
# outer (non-gutter) edge, and 0.125" on both top and bottom (0.25" total height).
BLEED_WIDTH_ADD_IN = 0.125
BLEED_HEIGHT_ADD_IN = 0.25

# How close an image edge must be to the physical page edge to count as
# "intended to bleed" rather than just a large image with a small margin.
EDGE_TOUCH_TOLERANCE_IN = 0.05


def closest_trim_size(width_in: float, height_in: float):
    best = None
    best_dist = None
    for w, h in TRIM_SIZES_IN:
        dist = abs(w - width_in) + abs(h - height_in)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best = (w, h)
    return best, best_dist


# --- Paperback cover spec --------------------------------------------------
# A paperback cover is one full-wrap PDF: back cover + spine + front cover,
# with bleed on all four outer edges. KDP calculates spine width from page
# count and paper stock; these per-page constants are from KDP's published
# cover calculator formulas (approximate — KDP's own calculator is the source
# of truth and may be adjusted by Amazon over time).
COVER_BLEED_IN = 0.125
SPINE_WIDTH_PER_PAGE_IN = {
    "white": 0.002252,
    "cream": 0.0025,
    "color": 0.002252,
}
PAPER_TYPE_LABELS = {
    "white": "white paper",
    "cream": "cream paper",
    "color": "premium color paper",
}
# Below this many pages, KDP advises against printing anything on the spine —
# it physically isn't wide enough to stay legible.
MIN_PAGES_FOR_SPINE_TEXT = 130
# Minimum spine width for any text to plausibly be legible at all.
MIN_SPINE_WIDTH_FOR_TEXT_IN = 0.25

# KDP overlays a barcode near the bottom-right of the back cover; this is the
# area to keep clear of essential text (background art can run underneath it).
BARCODE_WIDTH_IN = 2.0
BARCODE_HEIGHT_IN = 1.2
BARCODE_MARGIN_IN = 0.25


def cover_spine_width_in(page_count: int, paper_type: str) -> float:
    return page_count * SPINE_WIDTH_PER_PAGE_IN[paper_type]


def cover_dimensions_in(trim_w_in: float, trim_h_in: float, page_count: int,
                         paper_type: str):
    """Returns (total_width_in, total_height_in, spine_width_in) for the full
    wraparound cover PDF KDP expects."""
    spine_w = cover_spine_width_in(page_count, paper_type)
    total_w = (trim_w_in * 2) + spine_w + (COVER_BLEED_IN * 2)
    total_h = trim_h_in + (COVER_BLEED_IN * 2)
    return total_w, total_h, spine_w
