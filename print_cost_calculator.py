"""KDP print cost calculator. Shows authors the financial impact of their book choices.

Calculates per-unit printing cost for a given page count, trim size, and color mode.
Uses KDP's publicly available pricing structure.
"""

# KDP Print Cost Base Rates (as of 2024)
# Per-page cost varies by trim size and color
# Source: KDP pricing pages

_BW_COSTS_PER_PAGE = {
    # Trim size: cost per page (in USD, rounded to cents)
    "5x8": 0.02,      # Most common (novel size)
    "5.5x8.5": 0.025,
    "6x9": 0.03,      # Standard paperback
    "6.14x9.21": 0.03,  # A5 equivalent
    "7x10": 0.035,
    "8x10": 0.04,
    "8.5x11": 0.045,
}

_COLOR_COSTS_PER_PAGE = {
    # Color printing costs significantly more
    "5x8": 0.10,
    "5.5x8.5": 0.11,
    "6x9": 0.12,
    "6.14x9.21": 0.12,
    "7x10": 0.14,
    "8x10": 0.16,
    "8.5x11": 0.18,
}

# Cover costs
_COVER_COST_BW = 0.85  # B&W cover
_COVER_COST_COLOR = 2.50  # Full-color cover


def calculate_print_cost(page_count: int, trim_size: str, is_color: bool = False,
                        include_cover: bool = True) -> dict:
    """Calculate per-unit printing cost for a book.

    Args:
        page_count: Total pages in the book
        trim_size: "5x8", "6x9", "8.5x11", etc.
        is_color: True for color interior, False for B&W
        include_cover: True to add cover cost

    Returns:
        Dict with cost breakdown and per-copy royalty impact
    """
    trim_size = trim_size.strip().lower()

    # Get per-page cost
    cost_table = _COLOR_COSTS_PER_PAGE if is_color else _BW_COSTS_PER_PAGE
    if trim_size not in cost_table:
        # Fallback to 6x9 if size not found
        per_page_cost = cost_table.get("6x9", 0.03)
        trim_found = False
    else:
        per_page_cost = cost_table[trim_size]
        trim_found = True

    # Calculate interior cost
    interior_cost = page_count * per_page_cost

    # Add cover cost
    cover_cost = (_COVER_COST_COLOR if is_color else _COVER_COST_BW) if include_cover else 0
    total_cost = interior_cost + cover_cost

    # Format response
    return {
        "per_unit_cost": round(total_cost, 2),
        "interior_cost": round(interior_cost, 2),
        "cover_cost": round(cover_cost, 2),
        "page_count": page_count,
        "trim_size": trim_size,
        "is_color": is_color,
        "trim_size_found": trim_found,
        "breakdown": {
            "interior_pages": f"{page_count} pages × ${per_page_cost:.3f} = ${interior_cost:.2f}",
            "cover": f"Cover ({is_color and 'Color' or 'B&W'}): ${cover_cost:.2f}",
            "total": f"${total_cost:.2f} per copy",
        },
    }


def royalty_impact(list_price: float, print_cost: float, royalty_rate: float = 0.35) -> dict:
    """Show royalty earnings after printing costs.

    Args:
        list_price: Book price on Amazon
        print_cost: Per-unit printing cost
        royalty_rate: 0.35 for 35% royalty, 0.70 for 70% (70% requires <$9.99 or >$200)

    Returns:
        Dict with earnings breakdown
    """
    gross_royalty = list_price * royalty_rate
    net_royalty = gross_royalty - print_cost
    net_rate = (net_royalty / list_price * 100) if list_price > 0 else 0

    return {
        "list_price": list_price,
        "gross_royalty": round(gross_royalty, 2),
        "print_cost": round(print_cost, 2),
        "net_royalty": round(net_royalty, 2),
        "net_rate_percent": round(net_rate, 1),
        "royalty_rate": int(royalty_rate * 100),
        "per_sale_summary": (
            f"Price ${list_price:.2f} → Royalty ${gross_royalty:.2f} → "
            f"Print cost ${print_cost:.2f} → **Net: ${net_royalty:.2f}**"
        ),
    }


def suggest_price(print_cost: float, target_profit: float = 3.00, royalty_rate: float = 0.35) -> dict:
    """Suggest an optimal list price given print cost and desired profit.

    Args:
        print_cost: Per-unit printing cost
        target_profit: Desired profit per sale (e.g., $3 means author keeps $3/sale)
        royalty_rate: 0.35 or 0.70

    Returns:
        Dict with suggested price and earnings
    """
    # Solve for price: (price * royalty_rate) - print_cost = target_profit
    # price = (print_cost + target_profit) / royalty_rate
    suggested_price = (print_cost + target_profit) / royalty_rate

    # Round to common pricing tiers ($9.99, $14.99, etc.)
    price_tiers = [7.99, 8.99, 9.99, 10.99, 11.99, 12.99, 13.99, 14.99, 15.99, 16.99, 17.99, 18.99, 19.99]
    best_price = min(price_tiers, key=lambda p: abs(p - suggested_price))

    # Calculate actual profit at best price
    actual_royalty = best_price * royalty_rate
    actual_profit = actual_royalty - print_cost

    return {
        "suggested_price": round(suggested_price, 2),
        "recommended_price": best_price,
        "actual_profit": round(actual_profit, 2),
        "print_cost": round(print_cost, 2),
        "why": f"At ${best_price:.2f}, you'll make ${actual_profit:.2f} per sale after printing costs.",
    }


def compare_formats(page_count: int, list_price: float) -> dict:
    """Compare B&W vs Color to show financial impact.

    Shows how much more color printing costs and how it affects per-sale profit.
    """
    bw = calculate_print_cost(page_count, "6x9", is_color=False)
    color = calculate_print_cost(page_count, "6x9", is_color=True)

    bw_royalty = royalty_impact(list_price, bw["per_unit_cost"])
    color_royalty = royalty_impact(list_price, color["per_unit_cost"])

    extra_cost = color["per_unit_cost"] - bw["per_unit_cost"]
    profit_impact = color_royalty["net_royalty"] - bw_royalty["net_royalty"]

    return {
        "bw": {
            "cost": bw["per_unit_cost"],
            "profit_per_sale": bw_royalty["net_royalty"],
        },
        "color": {
            "cost": color["per_unit_cost"],
            "profit_per_sale": color_royalty["net_royalty"],
        },
        "difference": {
            "extra_cost": round(extra_cost, 2),
            "profit_impact": round(profit_impact, 2),
            "summary": f"Color costs ${extra_cost:.2f} more per book, reducing your profit by ${abs(profit_impact):.2f} per sale.",
        },
    }
