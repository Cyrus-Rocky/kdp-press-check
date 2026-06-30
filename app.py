import logging
import os
import uuid

from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.exceptions import RequestEntityTooLarge

from checker import run_all_checks
from cover_checker import run_all_cover_checks
from docx_checker import run_all_checks_docx
from epub_checker import run_all_checks_epub
from text_format_checker import run_all_checks_text_format
import kdp_rules as rules

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
            "or not a valid file of its type — try re-exporting it and upload again."
        )
        return redirect(url_for("index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("result.html", report=report, filename=file.filename, active_mode="interior")


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

    try:
        report = run_all_cover_checks(path, trim_w, trim_h, page_count, paper_type)
    except Exception:
        logger.exception("Failed to analyze cover upload %s (%s)", safe_name, file.filename)
        flash(
            "We couldn't read that file. It may be corrupted, password-protected, "
            "or not a valid PDF — try re-exporting it and upload again."
        )
        return redirect(url_for("cover_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("result.html", report=report, filename=file.filename, active_mode="cover")


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
            "We couldn't read that file. It may be corrupted or not a valid EPUB — "
            "try re-exporting it and upload again."
        )
        return redirect(url_for("kindle_index"))
    finally:
        if os.path.exists(path):
            os.remove(path)

    return render_template("result.html", report=report, filename=file.filename, active_mode="kindle")


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(_exc):
    flash("That file is larger than 200 MB. Choose a smaller file.")
    if request.path == "/check-cover":
        destination = "cover_index"
    elif request.path == "/check-kindle":
        destination = "kindle_index"
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
