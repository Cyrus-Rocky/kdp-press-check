import logging
import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, abort
from werkzeug.exceptions import RequestEntityTooLarge

from checker import run_all_checks
from cover_checker import run_all_cover_checks
from docx_checker import run_all_checks_docx
from epub_checker import run_all_checks_epub
from text_format_checker import run_all_checks_text_format
import affiliate
import kdp_rules as rules
import preview_renderer
from problem_solvers_data import CHECK_TO_CATEGORY

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".rtf", ".odt"}
LEGACY_DOC_EXT = {".doc"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kdp-checker")

GA_ID = os.environ.get("GA_MEASUREMENT_ID", "")

app.jinja_env.filters["affiliate"] = affiliate.apply


@app.context_processor
def inject_globals():
    return {"ga_id": GA_ID, "affiliate_enabled": affiliate.enabled()}


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
    except Exception:
        logger.exception("Failed to analyze upload %s (%s)", safe_name, file.filename)
        flash(
            "We couldn't read that file. It may be corrupted, password-protected, "
            "or not a valid file of its type, try re-exporting it and upload again."
        )
        return redirect(url_for("index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="interior", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY)


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
    except Exception:
        logger.exception("Failed to analyze cover upload %s (%s)", safe_name, file.filename)
        flash(
            "We couldn't read that file. It may be corrupted, password-protected, "
            "or not a valid PDF, try re-exporting it and upload again."
        )
        return redirect(url_for("cover_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="cover", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY,
                           cover_thumbnail_b64=cover_thumbnail_b64)


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

    return render_template("result.html", report=report, filename=file.filename,
                           active_mode="kindle", CHECK_TO_CATEGORY=CHECK_TO_CATEGORY)


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


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    flash("That file is larger than 200 MB. Choose a smaller file.")
    if request.path == "/check-cover":
        destination = "cover_index"
    elif request.path == "/check-kindle":
        destination = "kindle_index"
    elif request.path == "/check-preview":
        destination = "preview_index"
    else:
        destination = "index"
    return redirect(url_for(destination)), 413


@app.errorhandler(500)
def handle_server_error(exc):
    logger.exception("Unhandled server error")
    flash("Something went wrong on our end. Please try again.")
    return redirect(url_for("index")), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=int(os.environ.get("PORT", 5000)))
