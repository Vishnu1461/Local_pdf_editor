"""Local-only document store.

Every upload and every save happens inside a private temp directory on this
machine. Nothing is sent to a third party.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

MAX_UPLOAD_BYTES = 80 * 1024 * 1024


@dataclass
class StoredDocument:
    id: str
    name: str
    path: Path
    sha256: str
    size: int
    page_count: int
    pages: list[dict]
    existing_fields: list[dict] = field(default_factory=list)
    detected: list[dict] | None = None
    outputs: dict[str, Path] = field(default_factory=dict)
    output_names: dict[str, str] = field(default_factory=dict)


class DocumentStore:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="pdf-form-editor-"))
        self._docs: dict[str, StoredDocument] = {}

    def shutdown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def add(self, filename: str, data: bytes) -> StoredDocument:
        if not data:
            raise ValueError("empty upload")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("file exceeds 80 MB limit")
        if not data.lstrip().startswith(b"%PDF-"):
            raise ValueError("not a PDF file")

        doc = pymupdf.open(stream=data, filetype="pdf")
        if doc.needs_pass:
            doc.close()
            raise ValueError("password-protected PDFs are not supported")
        if doc.page_count == 0:
            doc.close()
            raise ValueError("PDF has no pages")
        pages = [
            {
                "index": i,
                "width": round(page.cropbox.width, 3),
                "height": round(page.cropbox.height, 3),
                "rotation": page.rotation,
            }
            for i, page in enumerate(doc)
        ]
        doc.close()

        doc_id = uuid.uuid4().hex
        directory = self.root / doc_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "source.pdf"
        path.write_bytes(data)

        from .acroform import extract_existing

        record = StoredDocument(
            id=doc_id,
            name=_safe_filename(filename or "document.pdf"),
            path=path,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            page_count=len(pages),
            pages=pages,
            existing_fields=extract_existing(str(path)),
        )
        self._docs[doc_id] = record
        return record

    def get(self, doc_id: str) -> StoredDocument:
        record = self._docs.get(doc_id)
        if record is None:
            raise KeyError(doc_id)
        return record

    def add_output(self, doc_id: str, filename: str, data: bytes) -> tuple[str, Path]:
        record = self.get(doc_id)
        output_id = uuid.uuid4().hex
        directory = record.path.parent / "outputs"
        directory.mkdir(exist_ok=True)
        path = directory / f"{output_id}.pdf"
        path.write_bytes(data)
        record.outputs[output_id] = path
        record.output_names[output_id] = _safe_filename(filename)
        return output_id, path

    def from_output(self, doc_id: str, output_id: str, name: str) -> StoredDocument:
        record = self.get(doc_id)
        path = record.outputs.get(output_id)
        if path is None or not path.exists():
            raise KeyError(output_id)
        return self.add(name, path.read_bytes())


def _safe_filename(name: str) -> str:
    name = Path(name).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    if not cleaned.lower().endswith(".pdf"):
        cleaned += ".pdf"
    return cleaned[:120] or "document.pdf"


store = DocumentStore()
