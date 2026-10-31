from __future__ import annotations

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_cors_origins_are_configurable(monkeypatch):
    monkeypatch.setenv("PDF_EDITOR_CORS_ORIGINS", "https://forms.example.com, https://admin.example.com")
    assert main._cors_origins() == ["https://forms.example.com", "https://admin.example.com"]

    monkeypatch.delenv("PDF_EDITOR_CORS_ORIGINS")
    assert main._cors_origins() == main.DEFAULT_ORIGINS


def test_rejects_non_pdf(client, tmp_path):
    bogus = tmp_path / "notes.txt"
    bogus.write_text("hello")
    with bogus.open("rb") as fh:
        res = client.post("/api/documents", files={"file": ("notes.txt", fh, "text/plain")})
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


def test_rejects_encrypted_pdf(client, tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    encrypted = tmp_path / "secret.pdf"
    doc.save(encrypted, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    doc.close()
    with encrypted.open("rb") as fh:
        res = client.post("/api/documents", files={"file": ("secret.pdf", fh, "application/pdf")})
    assert res.status_code == 400
    assert "password" in res.json()["detail"].lower()
