"""Pre-flight checklist: Final verification before uploading to KDP.

Returns a checklist of critical items to verify before hitting upload.
Gives authors confidence that they're ready.
"""


def generate_preflight_checklist(check_results: dict) -> dict:
    """Generate a pre-flight checklist from check results.

    Args:
        check_results: Dict returned from checker.run_all_checks()

    Returns:
        Dict with checklist items and overall readiness status
    """
    results = check_results.get("results", [])

    # Extract key checks
    checklist_items = []
    blocking_issues = []

    for result in results:
        title = result.get("title", "")
        ok = result.get("ok", False)
        is_blocking = not result.get("warning_only", False)

        # Map checks to checklist items
        mapping = {
            "Trim Size": ("✓ Trim Size", "Book dimensions match KDP standard"),
            "Page Size Consistency": ("✓ Page Consistency", "All pages are the same size"),
            "Margins": ("✓ Margins", "Text stays within safe zones"),
            "Fonts": ("✓ Font Embedding", "All fonts embedded in PDF"),
            "Image Resolution": ("✓ Image Quality", "All images are 300 DPI+"),
            "Bleed": ("✓ Bleed Setup", "Images/colors handled correctly at edges"),
            "Document Type": ("✓ Document Type", "File is recognized as a book"),
            "PDF Metadata": ("ℹ Metadata", "Title, Author set in PDF properties"),
        }

        if title in mapping:
            item_name, item_desc = mapping[title]
            checklist_items.append({
                "name": item_name,
                "description": item_desc,
                "status": "pass" if ok else "fail",
                "is_blocking": is_blocking,
                "message": result.get("summary", ""),
            })

            if not ok and is_blocking:
                blocking_issues.append(title)

    # Determine overall readiness
    blocking_count = sum(1 for item in checklist_items if not item["status"] == "pass" and item["is_blocking"])
    total_critical = sum(1 for item in checklist_items if item["is_blocking"])
    passed_critical = total_critical - blocking_count

    ready_to_upload = blocking_count == 0

    return {
        "title": "Pre-Flight Checklist",
        "ready_to_upload": ready_to_upload,
        "status": "ready" if ready_to_upload else "blocked",
        "blocking_issues": blocking_count,
        "critical_checks": total_critical,
        "passed_critical": passed_critical,
        "checklist": checklist_items,
        "blocking_titles": blocking_issues,
        "summary": (
            "✓ READY TO UPLOAD" if ready_to_upload
            else f"⚠ {blocking_count} BLOCKER(S) - Fix these before uploading"
        ),
        "instructions": (
            "All critical checks passed! Your book is ready for KDP. "
            "Review the quality tips below, then upload to KDP with confidence."
            if ready_to_upload
            else (
                f"Fix the {blocking_count} blocking issue(s) marked with ✗ above. "
                "Quality tips (marked with 💡) are optional but recommended."
            )
        ),
    }


def format_for_display(preflight: dict) -> dict:
    """Format preflight checklist for HTML display."""
    return {
        "overall_status": "READY" if preflight["ready_to_upload"] else "BLOCKED",
        "status_color": "#22c55e" if preflight["ready_to_upload"] else "#ef4444",
        "headline": preflight["summary"],
        "subheading": preflight["instructions"],
        "progress_percent": int((preflight["passed_critical"] / preflight["critical_checks"] * 100)
                                 if preflight["critical_checks"] > 0 else 0),
        "items": preflight["checklist"],
        "can_upload": preflight["ready_to_upload"],
        "blocking_count": preflight["blocking_issues"],
    }
