from __future__ import annotations

import hashlib
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import acroform, detection, templates
from .inspector import inspect_page
from .models import (
    DetectionResult,
    DocumentInfo,
    FieldSpec,
    PageInfo,
    SaveReport,
    SaveRequest,
    TemplateSummary,
)
from .storage import store

MAX_FIELDS = 3000


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    store.shutdown()


DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"]


def _cors_origins() -> list[str]:
    configured = [origin.strip() for origin in os.environ.get("PDF_EDITOR_CORS_ORIGINS", "").split(",")]
    return [origin for origin in configured if origin] or DEFAULT_ORIGINS


app = FastAPI(title="PDF Form Editor", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


def _info(record) -> DocumentInfo:
    return DocumentInfo(
        id=record.id,
        name=record.name,
        size=record.size,
        sha256=record.sha256,
        pageCount=record.page_count,
        pages=[PageInfo(**p) for p in record.pages],
        fields=[FieldSpec(**f) for f in record.existing_fields],
        templateMatch=(templates.find_match(record.pages, record.sha256) or {}).get("id"),
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/documents", response_model=DocumentInfo)
async def upload_document(file: UploadFile = File(...)) -> DocumentInfo:
    data = await file.read()
    try:
        record = store.add(file.filename or "document.pdf", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _info(record)


@app.get("/api/documents/{doc_id}", response_model=DocumentInfo)
def get_document(doc_id: str) -> DocumentInfo:
    try:
        return _info(store.get(doc_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")


@app.get("/api/documents/{doc_id}/file")
def get_file(doc_id: str) -> FileResponse:
    try:
        record = store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(record.path, media_type="application/pdf", filename=record.name)


@app.post("/api/documents/{doc_id}/detect", response_model=DetectionResult)
def detect(doc_id: str) -> DetectionResult:
    try:
        record = store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")

    if record.detected is None:
        doc = pymupdf.open(record.path)
        found: list[dict] = []
        for index, page in enumerate(doc):
            prims = inspect_page(page, index)
            found.extend(field.model_dump() for field in detection.detect_page(prims))
        doc.close()
        record.detected = found

    stats: dict[str, int] = {}
    for field in record.detected:
        stats[field["type"]] = stats.get(field["type"], 0) + 1
    stats["total"] = len(record.detected)
    return DetectionResult(fields=[FieldSpec(**f) for f in record.detected], stats=stats)


@app.get("/api/templates", response_model=list[TemplateSummary])
def list_templates() -> list[TemplateSummary]:
    return templates.summaries()


@app.post("/api/documents/{doc_id}/apply-template/{template_id}", response_model=list[FieldSpec])
def apply_template(doc_id: str, template_id: str) -> list[FieldSpec]:
    try:
        record = store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")
    template = templates.load_templates().get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    try:
        return templates.apply_template(template, record.pages)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/documents/{doc_id}/save", response_model=SaveReport)
def save(doc_id: str, request: SaveRequest) -> SaveReport:
    try:
        record = store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")
    if len(request.fields) > MAX_FIELDS:
        raise HTTPException(status_code=400, detail=f"too many fields (max {MAX_FIELDS})")

    _validate_fields(request.fields, record)
    flat = "flattened" if request.flatten else "filled"
    stem = Path(record.name).stem
    filename = _clean_filename(request.fileName) or f"{stem}-{flat}.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    output_path = record.path.parent / "outputs"
    output_path.mkdir(exist_ok=True)
    temp = output_path / f"pending-{doc_id}.pdf"
    try:
        result = acroform.save(str(record.path), str(temp), request.fields, request.flatten)
    except Exception as exc:  # surface a useful error instead of a 500 traceback
        raise HTTPException(status_code=500, detail=f"could not create form fields: {exc}") from exc

    data = temp.read_bytes()
    temp.unlink(missing_ok=True)
    output_id, _path = store.add_output(doc_id, filename, data)

    report = SaveReport(
        outputId=output_id,
        fileName=filename,
        downloadUrl=f"/api/documents/{doc_id}/outputs/{output_id}/file",
        sha256=hashlib.sha256(data).hexdigest(),
        pageCount=record.page_count,
        widgetCount=result["widgetCount"],
        flattened=request.flatten,
        warnings=result["warnings"],
        preservedPages=result["pages"] == record.page_count and not result["mismatches"],
    )
    return report


@app.get("/api/documents/{doc_id}/outputs/{output_id}/file")
def download_output(doc_id: str, output_id: str):
    try:
        record = store.get(doc_id)
        path = record.outputs.get(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="output not found")
    return FileResponse(path, media_type="application/pdf", filename=record.output_names.get(output_id, path.name))


@app.post("/api/documents/{doc_id}/outputs/{output_id}/reopen", response_model=DocumentInfo)
def reopen_output(doc_id: str, output_id: str) -> DocumentInfo:
    try:
        record = store.get(doc_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="document not found")
    path = record.outputs.get(output_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="output not found")
    reopened = store.add(f"{Path(record.name).stem}-reopened.pdf", path.read_bytes())
    return _info(reopened)


def _validate_fields(fields: list[FieldSpec], record) -> None:
    for field in fields:
        if field.page >= record.page_count:
            raise HTTPException(status_code=400, detail=f"field '{field.name}' is on a missing page")
        page = record.pages[field.page]
        x0, y0, x1, y1 = field.rect
        if x1 <= x0 or y1 <= y0:
            raise HTTPException(status_code=400, detail=f"field '{field.name}' has an invalid rectangle")
        if x0 < -1 or y0 < -1 or x1 > page["width"] + 1 or y1 > page["height"] + 1:
            raise HTTPException(status_code=400, detail=f"field '{field.name}' is outside page bounds")
        if field.type == "radio" and not (field.group or field.name):
            raise HTTPException(status_code=400, detail="radio field needs a group name")


def _clean_filename(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = "".join(ch for ch in Path(name).name if ch.isalnum() or ch in " ._-()").strip()
    cleaned = cleaned[:120]
    return cleaned or None
