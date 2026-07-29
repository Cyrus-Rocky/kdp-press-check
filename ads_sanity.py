"""Ads Sanity Checker (Pro).

Authors paste raw Amazon Ads campaign numbers and get a plain-English
diagnosis instead of a spreadsheet of unfamiliar acronyms. The most common,
costly mistake in every source we found researching this: panicking and
pausing or rewriting a campaign in the first 1-2 weeks, before Amazon's
algorithm has had time to gather data. This tool's first job is to talk
someone off that ledge when the data genuinely doesn't support panicking yet,
and to point at real, fixable causes when it does.
"""

# Amazon Ads needs real data to optimize; authors who judge (or pause) a
# campaign before this point are usually reacting to noise, not signal.
MIN_DAYS_BEFORE_JUDGING = 14
MIN_CLICKS_BEFORE_JUDGING = 20

# Rough day-30 profitability thresholds. ACOS (Ad Cost of Sale) above this
# means the ad is costing more than the royalty it's generating; royalty
# margin varies by book, so these are deliberately conservative bands, not a
# precise breakeven (which depends on the author's own royalty per copy).
ACOS_HEALTHY = 40
ACOS_WATCH = 70
ACOS_BAD = 100


def evaluate(spend: float, sales: float, clicks: int, impressions: int, days_running: int) -> dict:
    spend = max(0.0, spend)
    sales = max(0.0, sales)
    clicks = max(0, clicks)
    impressions = max(0, impressions)
    days_running = max(0, days_running)

    acos = (spend / sales * 100) if sales > 0 else (float("inf") if spend > 0 else 0.0)
    ctr = (clicks / impressions * 100) if impressions > 0 else 0.0
    cpc = (spend / clicks) if clicks > 0 else 0.0

    findings = []
    too_early = days_running < MIN_DAYS_BEFORE_JUDGING or clicks < MIN_CLICKS_BEFORE_JUDGING

    if too_early:
        findings.append({
            "severity": "note",
            "label": f"Too early to judge this campaign ({days_running} day(s), {clicks} click(s))",
            "detail": f"Amazon's algorithm needs at least {MIN_DAYS_BEFORE_JUDGING} days and "
                      f"roughly {MIN_CLICKS_BEFORE_JUDGING} clicks of real data before it can "
                      f"find the readers who convert. Pausing, rewriting copy, or raising bids "
                      f"now resets that clock; the single most common way authors waste ad "
                      f"budget is restarting a campaign before it's had a real chance to work.",
        })

    if impressions > 0 and ctr < 0.3:
        findings.append({
            "severity": "issue",
            "label": f"Click-through rate is low ({ctr:.2f}%)",
            "detail": "People are seeing your ad but not clicking. This is usually the cover or "
                      "title, not the targeting, if the ad isn't earning a click, no amount of "
                      "keyword tuning will fix it. Worth testing a different cover thumbnail or "
                      "ad copy before touching your bids.",
        })

    if clicks >= MIN_CLICKS_BEFORE_JUDGING:
        if sales <= 0:
            findings.append({
                "severity": "issue",
                "label": f"{clicks} clicks with zero sales",
                "detail": "People are clicking through to your book page and not buying. That "
                          "points at the book's Amazon listing itself, description, reviews, "
                          "price, or 'Look Inside' preview, rather than the ad targeting.",
            })
        elif acos > ACOS_BAD:
            findings.append({
                "severity": "issue",
                "label": f"ACOS is {acos:.0f}% — spending more than you're earning back",
                "detail": "At this rate you're losing money on every sale this campaign "
                          "produces. Check for broad-match keywords with no negative keywords "
                          "set, that's the single most common cause of budget bleeding into "
                          "irrelevant searches.",
            })
        elif acos > ACOS_WATCH:
            findings.append({
                "severity": "note",
                "label": f"ACOS is {acos:.0f}% — worth tightening, not yet an emergency",
                "detail": "You're spending close to what you earn back. Review your search term "
                          "report for clicks that aren't converting and add them as negative "
                          "keywords before increasing budget further.",
            })
        elif acos > ACOS_HEALTHY:
            findings.append({
                "severity": "ok",
                "label": f"ACOS is {acos:.0f}% — acceptable, keep monitoring",
                "detail": "Reasonable for a campaign still finding its footing. Recheck after "
                          "another week of data.",
            })
        else:
            findings.append({
                "severity": "ok",
                "label": f"ACOS is {acos:.0f}% — healthy",
                "detail": "This campaign is earning back more than it costs. Consider a modest "
                          "budget increase to see if it scales.",
            })

    if cpc > 0 and clicks < MIN_CLICKS_BEFORE_JUDGING and days_running >= MIN_DAYS_BEFORE_JUDGING:
        findings.append({
            "severity": "issue",
            "label": f"Very few clicks after {days_running} days ({clicks} total)",
            "detail": "Low impressions or low CTR is starving this campaign of data. Consider "
                      "broadening keywords slightly or raising the bid a small amount, large "
                      "jumps can overspend fast, so move in small steps.",
        })

    return {
        "acos": None if acos == float("inf") else round(acos, 1),
        "acos_display": "No sales yet" if acos == float("inf") else f"{acos:.0f}%",
        "ctr": round(ctr, 2),
        "cpc": round(cpc, 2),
        "too_early": too_early,
        "findings": findings,
    }
