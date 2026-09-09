"""PDF Converter — free, Adobe-free PDF → other formats (PyMuPDF / pypdf / python-docx)."""
from __future__ import annotations

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ProgressFn = Callable[[str, dict[str, Any] | None], None]

PDF_EXT = {".pdf"}

# id → label, output extension, multi-file (pages folder)
PRESETS: dict[str, dict[str, Any]] = {
    "txt": {
        "label": "Plain text (.txt)",
        "ext": ".txt",
        "multi": False,
        "needs": ["pypdf|pymupdf"],
    },
    "md": {
        "label": "Markdown (.md)",
        "ext": ".md",
        "multi": False,
        "needs": ["pypdf|pymupdf"],
    },
    "html": {
        "label": "HTML (.html)",
        "ext": ".html",
        "multi": False,
        "needs": ["pymupdf"],
    },
    "docx": {
        "label": "Word document (.docx)",
        "ext": ".docx",
        "multi": False,
        "needs": ["docx", "pypdf|pymupdf"],
    },
    "png": {
        "label": "PNG images (one per page)",
        "ext": ".png",
        "multi": True,
        "needs": ["pymupdf"],
    },
    "jpg": {
        "label": "JPEG images (one per page)",
        "ext": ".jpg",
        "multi": True,
        "needs": ["pymupdf"],
    },
    "webp": {
        "label": "WebP images (one per page)",
        "ext": ".webp",
        "multi": True,
        "needs": ["pymupdf", "pillow"],
    },
    "csv": {
        "label": "Tables → CSV (best-effort)",
        "ext": ".csv",
        "multi": False,
        "needs": ["pymupdf"],
    },
}

_jobs: dict[str, dict[str, Any]] = {}


def _have_pymupdf() -> bool:
    try:
        import pymupdf  # noqa: F401
        return True
    except ImportError:
        return False


def _pymupdf():
    import pymupdf
    return pymupdf


def _have_pypdf() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _have_docx() -> bool:
    try:
        import docx  # noqa: F401
        return True
    except ImportError:
        return False


def _have_pillow() -> bool:
    try:
        from PIL import Image  # noqa: F401
        return True
    except ImportError:
        return False


def engine_status() -> dict[str, Any]:
    """Report which free engines are installed (no Adobe)."""
    engines = {
        "pymupdf": _have_pymupdf(),
        "pypdf": _have_pypdf(),
        "python_docx": _have_docx(),
        "pillow": _have_pillow(),
    }
    ready = engines["pymupdf"] or engines["pypdf"]
    missing = [k for k, v in engines.items() if not v]
    install_hint = (
        "pip install pymupdf pypdf python-docx  (in toolbox .venv via INSTALL-PYTHON.bat)"
        if missing
        else ""
    )
    return {
        "ready": ready,
        "engines": engines,
        "missing": missing,
        "install_hint": install_hint,
        "adobe_free": True,
        "note": "Uses open-source libraries only — no Adobe Reader/Acrobat required.",
    }


def list_presets() -> list[dict[str, Any]]:
    status = engine_status()
    engines = status["engines"]
    out = []
    for pid, meta in PRESETS.items():
        avail = _preset_available(pid, engines)
        out.append({
            "id": pid,
            "label": meta["label"],
            "ext": meta["ext"],
            "multi": bool(meta.get("multi")),
            "available": avail,
        })
    return out


def _preset_available(preset: str, engines: dict[str, bool] | None = None) -> bool:
    engines = engines or engine_status()["engines"]
    meta = PRESETS.get(preset)
    if not meta:
        return False
    needs = meta.get("needs") or []
    for req in needs:
        if "|" in req:
            if not any(_engine_ok(part, engines) for part in req.split("|")):
                return False
        elif not _engine_ok(req, engines):
            return False
    return True


def _engine_ok(name: str, engines: dict[str, bool]) -> bool:
    key = name.strip().lower()
    if key in ("pymupdf", "fitz"):
        return bool(engines.get("pymupdf"))
    if key == "pypdf":
        return bool(engines.get("pypdf"))
    if key in ("docx", "python-docx", "python_docx"):
        return bool(engines.get("python_docx"))
    if key in ("pillow", "pil"):
        return bool(engines.get("pillow"))
    return False


def scan_folder(folder: str, recursive: bool = True) -> dict[str, Any]:
    base = Path(folder).resolve()
    if not base.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")
    files: list[dict[str, Any]] = []
    iterator = base.rglob("*") if recursive else base.iterdir()
    for p in iterator:
        if p.is_file() and p.suffix.lower() in PDF_EXT:
            try:
                st = p.stat()
                files.append({
                    "path": str(p),
                    "name": p.name,
                    "ext": p.suffix.lower(),
                    "size": st.st_size,
                    "type": "pdf",
                })
            except OSError:
                pass
    files.sort(key=lambda x: x["name"].lower())
    return {"folder": str(base), "count": len(files), "files": files}


def _output_base(src: Path, out_dir: Path | None) -> Path:
    dest_dir = out_dir or src.parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / src.stem


def _extract_text_pages(src: Path) -> list[str]:
    """Return plain text per page (prefer PyMuPDF layout text)."""
    if _have_pymupdf():
        fitz = _pymupdf()
        doc = fitz.open(str(src))
        try:
            pages = []
            for page in doc:
                t = page.get_text("text") or ""
                pages.append(t.rstrip())
            return pages
        finally:
            doc.close()
    if _have_pypdf():
        from pypdf import PdfReader
        reader = PdfReader(str(src))
        pages = []
        for page in reader.pages:
            try:
                pages.append((page.extract_text() or "").rstrip())
            except Exception:
                pages.append("")
        return pages
    raise RuntimeError(
        "No PDF text engine — install pymupdf or pypdf into the toolbox .venv "
        "(re-run INSTALL-PYTHON.bat after updating requirements.txt)"
    )


def _to_txt(src: Path, dest_base: Path) -> Path:
    pages = _extract_text_pages(src)
    out = dest_base.with_suffix(".txt")
    body = "\n\n".join(
        f"--- Page {i} ---\n{t}" if t else f"--- Page {i} ---\n"
        for i, t in enumerate(pages, start=1)
    )
    out.write_text(body + ("\n" if body else ""), encoding="utf-8", errors="replace")
    return out


def _to_md(src: Path, dest_base: Path) -> Path:
    pages = _extract_text_pages(src)
    out = dest_base.with_suffix(".md")
    parts = [f"# {src.stem}\n", f"_Converted from `{src.name}` (Adobe-free)_\n"]
    for i, t in enumerate(pages, start=1):
        parts.append(f"\n## Page {i}\n")
        parts.append(t if t else "*(no extractable text — may be a scan; try PNG/JPG then OCR)*\n")
    out.write_text("\n".join(parts), encoding="utf-8", errors="replace")
    return out


def _to_html(src: Path, dest_base: Path) -> Path:
    if not _have_pymupdf():
        # Fallback: wrap plain text
        pages = _extract_text_pages(src)
        out = dest_base.with_suffix(".html")
        blocks = []
        for i, t in enumerate(pages, start=1):
            esc = (
                t.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            blocks.append(f"<section><h2>Page {i}</h2><pre>{esc}</pre></section>")
        html = (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{src.stem}</title>"
            f"<style>body{{font-family:Segoe UI,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}}"
            f"pre{{white-space:pre-wrap;background:#f6f6f8;padding:12px;border-radius:8px}}</style>"
            f"</head><body><h1>{src.stem}</h1>{''.join(blocks)}</body></html>"
        )
        out.write_text(html, encoding="utf-8", errors="replace")
        return out

    fitz = _pymupdf()
    doc = fitz.open(str(src))
    try:
        parts = [
            f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{src.stem}</title>",
            "<style>body{font-family:Segoe UI,sans-serif;max-width:960px;margin:24px auto;padding:0 16px}"
            "section{margin:24px 0;padding-bottom:24px;border-bottom:1px solid #ddd}</style>",
            f"</head><body><h1>{src.stem}</h1>",
            f"<p><em>Converted from {src.name} — no Adobe required</em></p>",
        ]
        for i, page in enumerate(doc, start=1):
            # "html" preserves more structure than plain text
            chunk = page.get_text("html") or ""
            parts.append(f"<section><h2>Page {i}</h2>{chunk}</section>")
        parts.append("</body></html>")
        out = dest_base.with_suffix(".html")
        out.write_text("".join(parts), encoding="utf-8", errors="replace")
        return out
    finally:
        doc.close()


def _to_docx(src: Path, dest_base: Path) -> Path:
    if not _have_docx():
        raise RuntimeError(
            "python-docx not installed — re-run INSTALL-PYTHON.bat after updating requirements"
        )
    from docx import Document
    from docx.shared import Pt

    pages = _extract_text_pages(src)
    doc = Document()
    doc.core_properties.title = src.stem
    doc.core_properties.comments = "Converted Adobe-free by FAFO PDF Converter"
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(src.stem, level=0)
    doc.add_paragraph(f"Source: {src.name}")

    for i, t in enumerate(pages, start=1):
        doc.add_heading(f"Page {i}", level=1)
        if t.strip():
            # Split on blank lines into paragraphs
            for para in re.split(r"\n\s*\n", t):
                line = para.replace("\r\n", "\n").strip()
                if line:
                    doc.add_paragraph(line)
        else:
            doc.add_paragraph("(no extractable text on this page — scanned image?)")

    out = dest_base.with_suffix(".docx")
    doc.save(str(out))
    return out


def _to_images(src: Path, dest_base: Path, fmt: str, dpi: int = 150) -> list[Path]:
    if not _have_pymupdf():
        raise RuntimeError(
            "Page rendering needs pymupdf — re-run INSTALL-PYTHON.bat after updating requirements"
        )
    fitz = _pymupdf()

    fmt = fmt.lower().lstrip(".")
    if fmt == "jpeg":
        fmt = "jpg"
    folder = Path(str(dest_base) + f"_{fmt}_pages")
    folder.mkdir(parents=True, exist_ok=True)

    # 72 DPI is PDF default; scale matrix for requested DPI
    zoom = max(dpi, 72) / 72.0
    mat = fitz.Matrix(zoom, zoom)

    written: list[Path] = []
    doc = fitz.open(str(src))
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=mat, alpha=False)
            name = f"page_{i:03d}.{fmt if fmt != 'jpg' else 'jpg'}"
            out = folder / name
            if fmt == "webp":
                if not _have_pillow():
                    raise RuntimeError("WebP needs Pillow")
                from PIL import Image
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                img.save(str(out), "WEBP", quality=90)
            elif fmt == "jpg":
                pix.save(str(out), output="jpeg", jpg_quality=90)
            else:
                pix.save(str(out))
            written.append(out)
    finally:
        doc.close()
    return written


def _to_csv_tables(src: Path, dest_base: Path) -> Path:
    """Best-effort table dump via text blocks (not a full layout engine)."""
    if not _have_pymupdf():
        raise RuntimeError("CSV table extract needs pymupdf")
    fitz = _pymupdf()

    out = dest_base.with_suffix(".csv")
    rows_out: list[list[str]] = []
    doc = fitz.open(str(src))
    try:
        for pi, page in enumerate(doc, start=1):
            # "blocks" → lines with approximate columns via x positions
            blocks = page.get_text("dict") or {}
            for block in blocks.get("blocks") or []:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines") or []:
                    spans = line.get("spans") or []
                    text = "".join(s.get("text", "") for s in spans).strip()
                    if not text:
                        continue
                    # Heuristic: split on 2+ spaces or tabs
                    cells = re.split(r"\t+|\s{2,}", text)
                    cells = [c.strip() for c in cells if c.strip()]
                    if cells:
                        rows_out.append([f"p{pi}"] + cells)
    finally:
        doc.close()

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["page", "col1", "col2", "col3", "col4", "col5", "col6", "col7", "col8"])
        for row in rows_out:
            # pad / trim to header width-ish
            w.writerow(row[:9] if len(row) > 9 else row)
    return out


def convert_one(
    src: Path,
    preset: str,
    output_dir: Path | None = None,
    dpi: int = 150,
) -> dict[str, Any]:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    if not _preset_available(preset):
        raise RuntimeError(
            f"Preset '{preset}' unavailable — missing library. "
            + (engine_status().get("install_hint") or "")
        )
    if not src.is_file():
        raise FileNotFoundError(f"File not found: {src}")
    if src.suffix.lower() != ".pdf":
        raise ValueError("Input must be a .pdf file")

    dest_base = _output_base(src, output_dir)
    outputs: list[str] = []

    if preset == "txt":
        outputs.append(str(_to_txt(src, dest_base)))
    elif preset == "md":
        outputs.append(str(_to_md(src, dest_base)))
    elif preset == "html":
        outputs.append(str(_to_html(src, dest_base)))
    elif preset == "docx":
        outputs.append(str(_to_docx(src, dest_base)))
    elif preset in ("png", "jpg", "webp"):
        outputs.extend(str(p) for p in _to_images(src, dest_base, preset, dpi=dpi))
    elif preset == "csv":
        outputs.append(str(_to_csv_tables(src, dest_base)))
    else:
        raise ValueError(f"Unhandled preset: {preset}")

    return {
        "input": str(src),
        "ok": True,
        "outputs": outputs,
        "output": outputs[0] if outputs else None,
        "count": len(outputs),
    }


def convert_batch(
    files: list[str],
    preset: str = "txt",
    output_dir: str | None = None,
    dpi: int = 150,
    on_progress: ProgressFn | None = None,
) -> dict[str, Any]:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset: {preset}")
    if not engine_status()["ready"]:
        raise RuntimeError(
            "No PDF engine installed. Re-run INSTALL-PYTHON.bat after updating requirements.txt "
            "(needs pymupdf and/or pypdf)."
        )

    job_id = str(uuid.uuid4())[:8]
    out_path = Path(output_dir).resolve() if output_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    total = len(files)
    for i, f in enumerate(files):
        src = Path(f)
        if on_progress:
            on_progress(
                f"Converting {src.name} ({i + 1}/{total})…",
                {"index": i, "total": total, "file": src.name, "current": i + 1},
            )
        try:
            one = convert_one(src, preset, output_dir=out_path, dpi=dpi)
            results.append(one)
        except Exception as e:
            results.append({"input": str(src), "ok": False, "error": str(e), "outputs": []})

    succeeded = sum(1 for r in results if r.get("ok"))
    job = {
        "job_id": job_id,
        "preset": preset,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "succeeded": succeeded,
        "failed": total - succeeded,
        "results": results,
        "adobe_free": True,
    }
    _jobs[job_id] = job
    if on_progress:
        on_progress(f"Done — {succeeded}/{total} converted", {"job_id": job_id, "current": total, "total": total})
    return job


def get_job(job_id: str) -> dict[str, Any]:
    if job_id not in _jobs:
        raise FileNotFoundError("Job not found")
    return _jobs[job_id]


def convert_bytes_info() -> None:
    """Placeholder kept for API symmetry; conversion is path-based."""


def preview_png(path: str, page: int = 1, dpi: int = 110) -> dict[str, Any]:
    """First-page (or N) PNG preview for the converter UI."""
    if not _have_pymupdf():
        raise RuntimeError("Page preview needs pymupdf")
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    if src.suffix.lower() != ".pdf":
        raise ValueError("Preview only works on PDF files")
    fitz = _pymupdf()
    doc = fitz.open(str(src))
    try:
        pages = int(doc.page_count or 0)
        i = max(1, int(page or 1)) - 1
        if pages and i >= pages:
            i = pages - 1
        zoom = max(int(dpi or 110), 72) / 72.0
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return {
            "png": pix.tobytes("png"),
            "page": i + 1,
            "pages": pages,
            "width": pix.width,
            "height": pix.height,
            "name": src.name,
        }
    finally:
        doc.close()
    return None
