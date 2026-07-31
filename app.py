import logging
import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort, Response, session
from werkzeug.exceptions import RequestEntityTooLarge

from checker import run_all_checks
from cover_checker import run_all_cover_checks
from docx_checker import run_all_checks_docx
from epub_checker import run_all_checks_epub
from text_format_checker import run_all_checks_text_format
import affiliate
import newsletter
import pro_access
import recommended_tools
import kdp_rules as rules
import preview_renderer
import admin
import analytics
from problem_solvers_data import CHECK_TO_CATEGORY

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".rtf", ".odt"}
LEGACY_DOC_EXT = {".doc"}
# Cap uploads well below the free-tier's 512 MB RAM ceiling. Real KDP interiors
# and covers are almost always under this; allowing huge files just invites the
# out-of-memory crashes that take the whole instance down.
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "40"))
MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
# Pro-status session cookie: signed (tamper-proof via SECRET_KEY), httponly so
# JS can't read it, and long-lived so a subscriber isn't logged out every visit.
app.config["PERMANENT_SESSION_LIFETIME"] = 30 * 24 * 60 * 60  # 30 days
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
os.makedirs(UPLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kdp-checker")

GA_ID = os.environ.get("GA_MEASUREMENT_ID", "")
# Public base URL, used for canonical tags, Open Graph, and the sitemap. Set the
# SITE_URL env var to your custom domain once you have one.
SITE_URL = os.environ.get("SITE_URL", "https://kdp-press-check.onrender.com").rstrip("/")

# Every GET page, for the sitemap.
SITEMAP_ENDPOINTS = [
    "index", "cover_index", "kindle_index", "preview_index", "error_decoder",
    "keyword_linter", "margin_advisor", "isbn_helper", "description_formatter", "copyright_builder",
    "metadata_optimizer", "review_timeline", "royalty_calculator",
    "estimate_pages_index", "genre_checklist", "launch_checklist",
    "templates_page", "problem_solvers",
]

app.jinja_env.filters["affiliate"] = affiliate.apply

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def _asset_version(filename: str) -> str:
    """A cache-busting token from the file's last-modified time, so browsers
    always fetch fresh CSS/JS after a deploy instead of serving a stale copy."""
    try:
        return str(int(os.path.getmtime(os.path.join(_STATIC_DIR, filename))))
    except OSError:
        return "1"


@app.context_processor
def inject_asset_helper():
    def static_v(filename):
        return url_for("static", filename=filename) + "?v=" + _asset_version(filename)
    return {"static_v": static_v}


# Public contact address, shown in the footer and on About/Privacy when set.
# Leave unset (or set to your own) via the CONTACT_EMAIL env var.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()


@app.context_processor
def inject_globals():
    return {
        "ga_id": GA_ID,
        "site_url": SITE_URL,
        "contact_email": CONTACT_EMAIL,
        "affiliate_enabled": affiliate.enabled(),
        "newsletter_enabled": newsletter.enabled(),
        "newsletter_action": newsletter.FORM_ACTION,
        "newsletter_field": newsletter.EMAIL_FIELD,
        "recommended_tools": recommended_tools.visible(),
        "products_available": bool([p for p in _products() if p.get("buy_url", "").strip()]),
        "pro_enabled": pro_access.enabled(),
        "is_pro": pro_access.is_pro(session),
        "pro_price_display": pro_access.PRO_PRICE_DISPLAY,
    }


def _products():
    from products_data import PRODUCTS
    return PRODUCTS


@app.after_request
def set_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return resp


@app.route("/about")
def about():
    return render_template("about.html", active_mode="about")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", active_mode="privacy")


@app.route("/robots.txt")
def robots_txt():
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /preview-img/",
        f"Sitemap: {SITE_URL}/sitemap.xml",
    ])
    return Response(body, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    urls = "".join(
        f"<url><loc>{SITE_URL}{url_for(ep)}</loc><changefreq>weekly</changefreq></url>"
        for ep in SITEMAP_ENDPOINTS
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           + urls + "</urlset>")
    return Response(xml, mimetype="application/xml")


@app.route("/health", methods=["GET"])
def health():
    # Lightweight endpoint for uptime pingers (e.g. UptimeRobot) to keep the
    # free-tier instance awake without rendering a full page. Returns instantly.
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", active_mode="interior")


@app.route("/check", methods=["POST"])
def check():
    file = request.files.get("manuscript")
    if not file or file.filename == "":
        flash("Please choose a PDF file to upload.")
        return redirect(url_for("index"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext in LEGACY_DOC_EXT:
        flash(
            "Legacy .doc files aren't supported. Open it in Word and use File > Save As > "
            "Word Document (.docx), then upload that instead."
        )
        return redirect(url_for("index"))
    if ext not in ALLOWED_EXT:
        flash("Supported formats: PDF, Word (.docx), plain text (.txt), RTF, and OpenDocument (.odt).")
        return redirect(url_for("index"))

    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(path)

    try:
        if ext == ".docx":
            report = run_all_checks_docx(path)
        elif ext == ".pdf":
            report = run_all_checks(path)
        else:
            report = run_all_checks_text_format(path, ext)

        # Track analytics
        analytics.track_check("interior_check")
        analytics.track_upload(ext)
    except Exception as e:
        logger.exception("Failed to analyze upload %s (%s)", safe_name, file.filename)
        analytics.log_error(str(e), feature="interior_check")
        flash(
            "We couldn't read that file. It may be corrupted, password-protected, "
            "or not a valid file of its type, try re-exporting it and upload again."
        )
        return redirect(url_for("index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    report_job_id = _cache_report(report, file.filename, "interior")
    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="interior", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY,
                           report_job_id=report_job_id)


@app.route("/cover", methods=["GET"])
def cover_index():
    return render_template("cover_index.html", trim_sizes=rules.TRIM_SIZES_IN, active_mode="cover")


@app.route("/check-cover", methods=["POST"])
def check_cover():
    file = request.files.get("cover")
    if not file or file.filename == "":
        flash("Please choose a PDF cover file to upload.")
        return redirect(url_for("cover_index"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        flash("Cover files must be a PDF.")
        return redirect(url_for("cover_index"))

    try:
        trim_w = float(request.form.get("trim_w", ""))
        trim_h = float(request.form.get("trim_h", ""))
        page_count = int(request.form.get("page_count", ""))
        paper_type = request.form.get("paper_type", "")
    except ValueError:
        flash("Please fill in trim size and page count with valid numbers.")
        return redirect(url_for("cover_index"))

    if paper_type not in rules.SPINE_WIDTH_PER_PAGE_IN:
        flash("Please choose a paper type.")
        return redirect(url_for("cover_index"))
    if page_count < 1:
        flash("Page count must be at least 1.")
        return redirect(url_for("cover_index"))

    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(path)

    cover_thumbnail_b64 = None
    try:
        report = run_all_cover_checks(path, trim_w, trim_h, page_count, paper_type)
        # Render cover thumbnail (160px wide) for the result page
        try:
            import fitz as _fitz, base64 as _b64
            _doc = _fitz.open(path)
            _page = _doc[0]
            _scale = 160 / _page.rect.width
            _pix = _page.get_pixmap(matrix=_fitz.Matrix(_scale, _scale), alpha=False)
            cover_thumbnail_b64 = _b64.b64encode(_pix.tobytes("jpeg", jpg_quality=80)).decode()
            del _pix
            _doc.close()
        except Exception:
            pass

        # Track analytics
        analytics.track_check("cover_check")
        analytics.track_upload(".pdf")
    except Exception as e:
        logger.exception("Failed to analyze cover upload %s (%s)", safe_name, file.filename)
        analytics.log_error(str(e), feature="cover_check")
        flash(
            "We couldn't read that file. It may be corrupted, password-protected, "
            "or not a valid PDF, try re-exporting it and upload again."
        )
        return redirect(url_for("cover_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    report_job_id = _cache_report(report, file.filename, "cover")
    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="cover", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY,
                           cover_thumbnail_b64=cover_thumbnail_b64, report_job_id=report_job_id)


@app.route("/royalty-calculator", methods=["GET"])
def royalty_calculator():
    return render_template("royalty_calculator.html", active_mode="royalty")


@app.route("/estimate-pages", methods=["GET"])
def estimate_pages_index():
    return render_template("page_estimator.html", active_mode="estimate")


def _human_file_size(n_bytes: int) -> str:
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.0f} KB"
    return f"{n_bytes / (1024 * 1024):.1f} MB"


def _docx_saved_page_count(path: str):
    """Word records the page count it last computed in docProps/app.xml. A .docx
    stores no live page geometry, so this saved value is the only real page
    count available without re-rendering the file. Returns None if the file has
    no usable saved count (e.g. it was generated by a tool that never
    paginated it)."""
    import zipfile
    import re as _re
    try:
        with zipfile.ZipFile(path) as z:
            app_xml = z.read("docProps/app.xml").decode("utf-8", "ignore")
    except (KeyError, zipfile.BadZipFile, OSError):
        return None
    m = _re.search(r"<Pages>(\d+)</Pages>", app_xml)
    if not m:
        return None
    pages = int(m.group(1))
    return pages if pages > 0 else None


@app.route("/estimate-pages", methods=["POST"])
def estimate_pages():
    file = request.files.get("manuscript")
    if not file or file.filename == "":
        flash("Please choose a Word (.docx) file.")
        return redirect(url_for("estimate_pages_index"))
    if not file.filename.lower().endswith(".docx"):
        flash("Document details only work with Word (.docx) files.")
        return redirect(url_for("estimate_pages_index"))

    safe_name = f"{uuid.uuid4().hex}.docx"
    path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(path)

    try:
        from docx import Document as _DocxDoc
        file_size = _human_file_size(os.path.getsize(path))
        pages = _docx_saved_page_count(path)

        _doc = _DocxDoc(path)
        # Count from the actual paragraph text so words/characters always
        # reflect the current content, not a possibly-stale saved figure.
        para_texts = [p.text for p in _doc.paragraphs]
        word_count = sum(len(t.split()) for t in para_texts)
        char_with_spaces = sum(len(t) for t in para_texts)
        char_no_spaces = sum(len(t.replace(" ", "").replace("\t", "")) for t in para_texts)
        para_count = sum(1 for t in para_texts if t.strip())

        result = {
            "pages": pages,  # None if the file has no saved page count
            "word_count": word_count,
            "char_count": char_with_spaces,
            "char_count_no_spaces": char_no_spaces,
            "para_count": para_count,
            "file_size": file_size,
        }
    except Exception:
        logger.exception("Document details failed for %s", safe_name)
        flash("We couldn't read that Word file, try saving it as .docx again.")
        return redirect(url_for("estimate_pages_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("page_estimator.html", active_mode="estimate",
                           result=result, filename=file.filename)


@app.route("/error-decoder", methods=["GET"])
def error_decoder():
    return render_template("error_decoder.html", active_mode="decoder")


@app.route("/keyword-linter", methods=["GET"])
def keyword_linter():
    return render_template("keyword_linter.html", active_mode="keywords")


@app.route("/margin-advisor", methods=["GET"])
def margin_advisor():
    return render_template("margin_advisor.html", active_mode="margins")


@app.route("/isbn-helper", methods=["GET"])
def isbn_helper():
    return render_template("isbn_helper.html", active_mode="isbn")


@app.route("/description-formatter", methods=["GET"])
def description_formatter():
    return render_template("description_formatter.html", active_mode="description")


@app.route("/copyright-builder", methods=["GET"])
def copyright_builder():
    return render_template("copyright_page_builder.html", active_mode="copyright")


@app.route("/metadata-optimizer", methods=["GET"])
def metadata_optimizer():
    return render_template("metadata_optimizer.html", active_mode="metadata")


@app.route("/review-timeline", methods=["GET"])
def review_timeline():
    return render_template("review_timeline.html", active_mode="timeline")


@app.route("/launch-checklist", methods=["GET"])
def launch_checklist():
    return render_template("launch_checklist.html", active_mode="launch")


@app.route("/templates", methods=["GET"])
def templates_page():
    from products_data import PRODUCTS
    return render_template("products.html", active_mode="products", products=PRODUCTS)


@app.route("/genre-checklist", methods=["GET"])
def genre_checklist():
    return render_template("genre_checklist.html", active_mode="genre")


@app.route("/pro", methods=["GET"])
def pro_landing():
    if pro_access.is_pro(session):
        return redirect(url_for("pro_dashboard"))
    return render_template("pro_landing.html", active_mode="pro")


@app.route("/pro/checkout", methods=["POST"])
def pro_checkout():
    if not pro_access.enabled():
        flash("Pro isn't available yet, check back soon.")
        return redirect(url_for("pro_landing"))
    try:
        url = pro_access.create_checkout_url(
            success_url=SITE_URL + url_for("pro_success"),
            cancel_url=SITE_URL + url_for("pro_landing"),
        )
    except Exception:
        logger.exception("Failed to create Stripe checkout session")
        flash("We couldn't start checkout just now. Please try again in a moment.")
        return redirect(url_for("pro_landing"))
    return redirect(url)


@app.route("/pro/success", methods=["GET"])
def pro_success():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return redirect(url_for("pro_landing"))
    try:
        email, customer_id = pro_access.email_from_checkout_session(session_id)
    except Exception:
        logger.exception("Failed to verify Stripe checkout session")
        email, customer_id = None, None
    if not email:
        flash("We couldn't confirm that payment. If you were charged, email us and we'll sort it out.")
        return redirect(url_for("pro_landing"))
    pro_access.mark_session_pro(session, email, customer_id)
    flash("You're in. Welcome to Pro.")
    return redirect(url_for("pro_dashboard"))


@app.route("/pro/login", methods=["GET", "POST"])
def pro_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash("Enter the email you subscribed with.")
            return redirect(url_for("pro_login"))
        customer_id = pro_access.active_subscription(email)
        if customer_id:
            pro_access.mark_session_pro(session, email, customer_id)
            flash("Welcome back.")
            return redirect(url_for("pro_dashboard"))
        flash("We couldn't find an active Pro subscription for that email.")
        return redirect(url_for("pro_login"))
    return render_template("pro_login.html", active_mode="pro")


@app.route("/pro/logout", methods=["POST"])
def pro_logout():
    pro_access.clear_session_pro(session)
    flash("Signed out of Pro on this device.")
    return redirect(url_for("pro_landing"))


@app.route("/pro/dashboard", methods=["GET"])
def pro_dashboard():
    if not pro_access.is_pro(session):
        return redirect(url_for("pro_login"))
    return render_template("pro_dashboard.html", active_mode="pro")


@app.route("/pro/billing", methods=["POST"])
def pro_billing():
    if not pro_access.is_pro(session):
        return redirect(url_for("pro_login"))
    try:
        url = pro_access.create_billing_portal_url(
            session["pro_customer_id"], return_url=SITE_URL + url_for("pro_dashboard")
        )
    except Exception:
        logger.exception("Failed to create Stripe billing portal session")
        flash("Couldn't open billing management right now, try again shortly.")
        return redirect(url_for("pro_dashboard"))
    return redirect(url)


def pro_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not pro_access.is_pro(session):
            flash("That tool is part of KDP Press Check Pro.")
            return redirect(url_for("pro_landing"))
        return view(*args, **kwargs)
    return wrapped


# In-memory cache so a Pro subscriber can download a branded PDF of the check
# they just ran, without re-uploading. Small (titles/summaries only, no file
# bytes) and short-lived, so a plain dict keyed by a random id is enough, no
# database needed. Same pattern as preview_renderer's on-disk job cache.
_REPORT_CACHE = {}
_REPORT_CACHE_TTL = 30 * 60  # 30 minutes


def _cache_report(report, filename, mode_label):
    import time
    job_id = uuid.uuid4().hex
    now = time.time()
    # opportunistic cleanup of expired entries
    for k in [k for k, v in _REPORT_CACHE.items() if now - v["ts"] > _REPORT_CACHE_TTL]:
        _REPORT_CACHE.pop(k, None)
    _REPORT_CACHE[job_id] = {"report": report, "filename": filename, "mode": mode_label, "ts": now}
    return job_id


_MANUSCRIPT_TEXT_EXT = {".docx", ".txt", ".rtf", ".odt"}


def _extract_manuscript_text(file_storage) -> str:
    """Extracts plain text from an uploaded manuscript for text-only analysis
    (no print geometry needed). Raises ValueError for unsupported types."""
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in _MANUSCRIPT_TEXT_EXT:
        raise ValueError("Unsupported file type: " + ext)
    tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")
    file_storage.save(tmp_path)
    try:
        if ext == ".docx":
            from docx import Document as _DocxDoc
            doc = _DocxDoc(tmp_path)
            return "\n".join(p.text for p in doc.paragraphs)
        import formats
        return formats.extract(tmp_path, ext)["full_text"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.route("/pro/ai-disclosure", methods=["GET"])
@pro_required
def ai_disclosure_advisor():
    return render_template("pro_ai_disclosure.html", active_mode="pro")


@app.route("/pro/ai-disclosure/quiz", methods=["POST"])
@pro_required
def ai_disclosure_quiz():
    import ai_disclosure
    used_ai = request.form.get("used_ai") == "yes"
    ai_wrote_it = request.form.get("ai_wrote_it") == "yes"
    quiz_result = ai_disclosure.classify_disclosure(used_ai, ai_wrote_it)
    analytics.track_pro_check("ai_disclosure_quiz")
    return render_template("pro_ai_disclosure.html", active_mode="pro", quiz_result=quiz_result,
                            used_ai=request.form.get("used_ai"), ai_wrote_it=request.form.get("ai_wrote_it"))


@app.route("/pro/ai-disclosure/scan", methods=["POST"])
@pro_required
def ai_disclosure_scan():
    import ai_disclosure
    file = request.files.get("manuscript")
    if not file or file.filename == "":
        flash("Choose a manuscript file first (.docx, .txt, .rtf, or .odt).")
        return redirect(url_for("ai_disclosure_advisor"))
    try:
        text = _extract_manuscript_text(file)
    except ValueError:
        flash("That file type isn't supported. Use .docx, .txt, .rtf, or .odt.")
        return redirect(url_for("ai_disclosure_advisor"))
    except Exception:
        logger.exception("AI disclosure scan failed to read %s", file.filename)
        flash("We couldn't read that file. It may be corrupted, try re-saving and uploading again.")
        return redirect(url_for("ai_disclosure_advisor"))
    scan_result = ai_disclosure.scan_manuscript(text)
    analytics.track_pro_check("ai_disclosure_scan")
    return render_template("pro_ai_disclosure.html", active_mode="pro",
                            scan_result=scan_result, scan_filename=file.filename)


@app.route("/pro/ads-checker", methods=["GET"])
@pro_required
def ads_sanity_checker():
    return render_template("pro_ads_checker.html", active_mode="pro")


@app.route("/pro/ads-checker/check", methods=["POST"])
@pro_required
def ads_sanity_check():
    import ads_sanity

    def _num(name, cast=float):
        try:
            return cast(request.form.get(name, "0") or "0")
        except ValueError:
            return 0

    inputs = {
        "spend": _num("spend"),
        "sales": _num("sales"),
        "clicks": _num("clicks", int),
        "impressions": _num("impressions", int),
        "days_running": _num("days_running", int),
    }
    ads_result = ads_sanity.evaluate(**inputs)
    return render_template("pro_ads_checker.html", active_mode="pro", ads_result=ads_result, form=inputs)


def _readiness_pct(report: dict) -> int:
    """Mirrors the readiness-% calc in result.html's Jinja: 100, minus 16 per
    failed blocking check and 5 per failed advisory check, floored at 10."""
    score = 100
    for r in report.get("results", []):
        if not r.get("ok"):
            score -= 5 if r.get("warning_only") else 16
    return max(score, 10)


@app.route("/pro/report/<job_id>.pdf", methods=["GET"])
@pro_required
def download_report_pdf(job_id):
    entry = _REPORT_CACHE.get(job_id)
    if not entry:
        flash("That report has expired. Run the check again to download a fresh copy.")
        return redirect(url_for("index"))
    import pdf_report
    report = dict(entry["report"])
    report["readiness_pct"] = _readiness_pct(report)
    pdf_bytes = pdf_report.build_report_pdf(report, entry["filename"], entry["mode"], SITE_URL)
    return Response(pdf_bytes, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="kdp-press-check-report.pdf"'
    })


@app.route("/pro/category-finder", methods=["GET"])
@pro_required
def category_trap_finder():
    import category_finder as cf
    genre = request.args.get("genre", "fiction")
    return render_template("pro_category_finder.html", active_mode="pro",
                            genre_labels=cf.GENRE_LABELS, selected_genre=genre,
                            examples=cf.examples_for(genre),
                            verdict_label=cf.VERDICT_LABEL, verdict_severity=cf.VERDICT_SEVERITY)


@app.route("/pro/category-finder/check", methods=["POST"])
@pro_required
def category_finder_check():
    import category_finder as cf
    genre = request.form.get("genre", "fiction")
    custom_path = request.form.get("custom_path", "")
    custom_result = cf.evaluate_custom_path(custom_path)
    return render_template("pro_category_finder.html", active_mode="pro",
                            genre_labels=cf.GENRE_LABELS, selected_genre=genre,
                            examples=cf.examples_for(genre),
                            verdict_label=cf.VERDICT_LABEL, verdict_severity=cf.VERDICT_SEVERITY,
                            custom_path=custom_path, custom_result=custom_result)


@app.route("/kindle", methods=["GET"])
def kindle_index():
    return render_template("kindle_index.html", active_mode="kindle")


@app.route("/check-kindle", methods=["POST"])
def check_kindle():
    file = request.files.get("ebook")
    if not file or file.filename == "":
        flash("Please choose an EPUB file to upload.")
        return redirect(url_for("kindle_index"))

    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".epub":
        flash("Kindle files must be a .epub file (export from Kindle Create, Vellum, Calibre, etc.).")
        return redirect(url_for("kindle_index"))

    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, safe_name)
    file.save(path)

    try:
        report = run_all_checks_epub(path)
    except Exception:
        logger.exception("Failed to analyze kindle upload %s (%s)", safe_name, file.filename)
        flash(
            "We couldn't read that file. It may be corrupted or not a valid EPUB, "
            "try re-exporting it and upload again."
        )
        return redirect(url_for("kindle_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    report_job_id = _cache_report(report, file.filename, "kindle")
    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="kindle", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY,
                           report_job_id=report_job_id)


@app.route("/preview", methods=["GET"])
def preview_index():
    return render_template("preview_index.html", active_mode="preview")


@app.route("/check-preview", methods=["POST"])
def check_preview():
    interior_file = request.files.get("interior")
    cover_file = request.files.get("cover")

    if not interior_file or interior_file.filename == "":
        flash("Please choose an interior PDF to preview.")
        return redirect(url_for("preview_index"))

    ext = os.path.splitext(interior_file.filename)[1].lower()
    if ext != ".pdf":
        flash("The interior file must be a PDF.")
        return redirect(url_for("preview_index"))

    interior_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.pdf")
    interior_file.save(interior_path)
    cover_path = None

    if cover_file and cover_file.filename:
        cext = os.path.splitext(cover_file.filename)[1].lower()
        if cext == ".pdf":
            cover_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.pdf")
            cover_file.save(cover_path)

    job_id = uuid.uuid4().hex
    check_report = None
    margin_report = None
    try:
        # Run compliance check + margin scan BEFORE rendering (file still on disk)
        try:
            check_report = run_all_checks(interior_path)
        except Exception:
            logger.warning("Preview compliance check failed", exc_info=True)
        try:
            margin_report = preview_renderer.check_page_margins(interior_path)
        except Exception:
            logger.warning("Preview margin scan failed", exc_info=True)

        meta = preview_renderer.render_job(UPLOAD_DIR, job_id, interior_path, cover_path)
    except preview_renderer.PreviewTooLargeError as exc:
        flash(f"This PDF has {exc.page_count} pages, which is too long to preview here "
              f"(limit is {preview_renderer.MAX_PREVIEW_PAGES}). The Interior Check still "
              f"works on books this size, use that for the full report.")
        return redirect(url_for("preview_index"))
    except Exception:
        logger.exception("Preview render failed")
        flash("We couldn't render that PDF. It may be corrupted or password-protected.")
        return redirect(url_for("preview_index"))
    finally:
        if os.path.exists(interior_path):
            os.remove(interior_path)
        if cover_path and os.path.exists(cover_path):
            os.remove(cover_path)

    from problem_solvers_data import SOLVERS, CHECK_TO_CATEGORY as C2C

    def best_solver(check_title):
        cat = C2C.get(check_title, "formatting")
        matches = [s for s in SOLVERS if cat in s["categories"]]
        return matches[0] if matches else SOLVERS[0]

    return render_template(
        "preview_result.html",
        active_mode="preview",
        interior_filename=interior_file.filename,
        job_id=job_id,
        interior_meta=meta["interior"],
        cover_meta=meta.get("cover"),
        check_report=check_report,
        margin_report=margin_report,
        best_solver=best_solver,
    )


@app.route("/preview-img/<job_id>/<kind>/<int:page_num>")
def preview_img(job_id, kind, page_num):
    if kind not in ("interior", "cover"):
        abort(404)
    # Sanitise job_id, must be a 32-char hex string
    if not job_id.isalnum() or len(job_id) != 32:
        abort(404)
    path = preview_renderer.page_file(UPLOAD_DIR, job_id, kind, page_num)
    if path is None:
        abort(404)
    return send_file(path, mimetype="image/jpeg",
                     max_age=1800, conditional=True)


@app.route("/problem-solvers")
def problem_solvers():
    from problem_solvers_data import SOLVERS, CATEGORIES
    cat = request.args.get("cat", "all")
    return render_template("problem_solvers.html", active_mode="solvers",
                           solvers=SOLVERS, categories=CATEGORIES, active_cat=cat)


# ──────────────────────────────────────────────────────────────────────────────
# ADMIN DASHBOARD ROUTES
# ──────────────────────────────────────────────────────────────────────────────

@app.route("/admin", methods=["GET"])
@admin.admin_required
def admin_dashboard():
    """Main admin dashboard showing analytics, subscribers, and system health."""
    subs = admin.fetch_stripe_subscribers()
    stats = analytics.get_stats()
    top = analytics.get_top_features(n=5)
    max_checks = max(top.values()) if top else 1
    max_pro = max(stats['pro_checks_by_feature'].values()) if stats['pro_checks_by_feature'] else 1
    max_uploads = max(stats['uploads_by_format'].values()) if stats['uploads_by_format'] else 1

    active_count = sum(1 for s in subs if s['status'] == 'active')
    trial_count = sum(1 for s in subs if s['status'] == 'trialing')

    return render_template("admin_dashboard.html",
                           subscribers=subs,
                           subscriber_count=len(subs),
                           active_sub_count=active_count,
                           trial_count=trial_count,
                           mrr=admin.calculate_mrr(subs),
                           stats=stats,
                           top_features=top,
                           max_checks=max_checks,
                           max_pro=max_pro,
                           max_uploads=max_uploads)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login page."""
    if request.method == "POST":
        password = request.form.get("password", "")
        success, msg = admin.verify_admin_password(password)
        if success:
            admin.mark_admin_authenticated(session)
            flash("Welcome, admin!")
            return redirect(url_for("admin_dashboard"))
        else:
            flash(f"Login failed: {msg}", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["GET", "POST"])
def admin_logout():
    """Log out of admin panel."""
    session.pop("admin_authenticated", None)
    session.pop("admin_auth_time", None)
    flash("Logged out of admin panel.")
    return redirect(url_for("index"))


@app.route("/admin/refund", methods=["POST"])
@admin.admin_required
def admin_refund():
    """Issue a refund for a subscription."""
    sub_id = request.form.get("subscription_id", "")
    success, msg = admin.refund_subscription(sub_id, reason="refund")
    if success:
        flash(f"Refund issued: {msg}")
    else:
        flash(f"Refund failed: {msg}", "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/cancel", methods=["POST"])
@admin.admin_required
def admin_cancel():
    """Cancel a subscription."""
    sub_id = request.form.get("subscription_id", "")
    success, msg = admin.cancel_subscription(sub_id)
    if success:
        flash(f"Subscription cancelled: {msg}")
    else:
        flash(f"Cancellation failed: {msg}", "error")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    flash(f"That file is larger than {MAX_UPLOAD_MB} MB. Export a lighter file "
          f"(compress oversized images to 300 DPI) and try again.")
    if request.path == "/check-cover":
        destination = "cover_index"
    elif request.path == "/check-kindle":
        destination = "kindle_index"
    elif request.path == "/check-preview":
        destination = "preview_index"
    else:
        destination = "index"
    return redirect(url_for(destination)), 413


@app.errorhandler(404)
def handle_not_found(_exc):
    return render_template("404.html", active_mode=""), 404


@app.errorhandler(500)
def handle_server_error(exc):
    logger.exception("Unhandled server error")
    flash("Something went wrong on our end. Please try again.")
    return redirect(url_for("index")), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=int(os.environ.get("PORT", 5000)))
