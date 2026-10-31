# PDF Form Editor

A local-first web application that turns existing PDFs into PDFs with **real AcroForm fields**. It opens the original document, detects blank areas, lets you review and edit them, and writes standard form widgets that work in Adobe Acrobat, browsers, Preview, and other PDF readers.

The original page content is never rasterized or recreated. Text, vector graphics, borders, images, and page dimensions stay untouched; fields are added as annotations on top.

![Field detection with editable overlays](docs/screenshots/editor.png)

![Filled fields with the properties panel](docs/screenshots/editing.png)

## Features

- **Open existing PDFs without changing their appearance.** Pages are rendered with PDF.js; the file itself is only modified when you save a copy.
- **Automatic field detection.** Finds white input boxes, underscore runs, horizontal rules, checkboxes, and nearby printed labels. Every proposal carries a confidence value and can be reviewed, edited, or deleted.
- **Optional local templates.** For forms you process repeatedly, a JSON template can pin exact rectangles and field types. Templates are loaded from `backend/app/templates/` when present; none are bundled with the public repository.
- **Manual authoring.** Draw new fields with the toolbar: text, paragraph, date, number, email, checkbox, radio group, dropdown, signature, and image.
- **Inline editing.** Double-click a field and type. Text shrinks to fit, respects alignment and maximum length, and commits with Enter (Ctrl/Cmd+Enter for multiline).
- **Full field properties.** Label, name, type, font size (0 = auto), maximum characters, alignment, white or transparent background, required flag, dropdown options, and radio groups.
- **Move, resize, delete, undo, redo.** Arrow keys nudge by 1 pt (Shift = 10 pt); Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z or Ctrl/Cmd+Y.
- **Save a copy, never the original.** The backend writes a new file on every save and lets you reopen it directly in the editor.
- **Flatten when needed.** Produces a copy with field values baked into the page content and no remaining widgets.
- **Canonical geometry.** Field rectangles are stored in unrotated PDF points relative to the crop box, so positions survive zoom, window resizing, saving, and reopening.

## Privacy and security

PDF Form Editor is designed for documents that must not leave the machine:

- All parsing, detection, editing, and PDF generation happen locally.
- There are no telemetry calls, no external AI services, and no document uploads to third parties.
- Uploaded files and saved copies are written to a private directory created with the operating system's temporary-file API.
- The application does not include authentication. Run it on localhost, or put it behind an authenticated reverse proxy with TLS before exposing it to anyone else.
- Never commit documents, filled forms, or `test-data/` to a repository. The supplied `.gitignore` excludes PDFs and test data for this reason.
- No third-party form template, form image, or brand-specific asset is distributed with this repository.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities and the deployment assumptions.

## How it works

```text
┌─────────────────────────────────────────────┐
│ Browser                                     │
│  React 19 + TypeScript + PDF.js             │
│  - renders pages and the original text      │
│  - draws the editable field layer           │
│  - converts pointer positions with the      │
│    PDF.js viewport (never hardcoded pixels) │
└───────────────────┬─────────────────────────┘
                    │ HTTP JSON / PDF
┌───────────────────▼─────────────────────────┐
│ FastAPI backend (Python)                    │
│  inspector.py   page geometry and words     │
│  detection.py   geometric field proposals   │
│  templates.py   pinned geometry per form    │
│  acroform.py    widget creation and verify  │
│  storage.py     temporary files and IDs     │
└───────────────────┬─────────────────────────┘
                    │
            OS temporary directory
```

Detection proposes; it never commits. The frontend keeps the authoritative field list and sends it on save. Before returning a save report, the backend reopens the generated document and verifies that every widget exists on the expected page within 1.5 pt. Any mismatch is returned as a warning and marks the report as not fully preserved, so an incomplete save is never reported as a clean one.

### Coordinate system

Field rectangles use PDF points in the page's unrotated crop-box space, with the origin at the top-left and y increasing downward. This is the same space PyMuPDF uses, so no conversion happens on the backend. The frontend converts only through the PDF.js viewport; see `frontend/src/coordinates.ts`.

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript 7, Vite 8, PDF.js (`pdfjs-dist` 6) |
| Backend | Python, FastAPI, Pydantic 2, Uvicorn |
| PDF processing | PyMuPDF (MuPDF) |
| Tests | pytest, FastAPI TestClient, Playwright (development driver) |
| Linting | oxlint |

## Prerequisites

- Python 3.11 or newer (tested with 3.14).
- Node.js 20.19 or newer (tested with 24) and npm.
- Git.

PDF.js runs entirely in the browser. No native browser automation is required for normal use; Playwright is only a development dependency.

## Installation

```bash
git clone https://github.com/<your-account>/pdf-form-editor.git
cd pdf-form-editor
```

### Backend

```bash
python -m venv backend/.venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
backend\.venv\Scripts\Activate.ps1

# macOS / Linux
source backend/.venv/bin/activate
```

Install dependencies and start the API:

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000`; its health endpoint is `GET /api/health`. Run Uvicorn from `backend/` so the `app` package resolves.

### Frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

If your API runs elsewhere, copy the example environment file before building or starting the dev server:

```bash
cd frontend
cp .env.example .env.local
```

## Configuration

| Variable | Used by | Default | Description |
| --- | --- | --- | --- |
| `VITE_API_BASE` | Frontend | `http://127.0.0.1:8000` | Base URL of the backend API. Read at build/dev-server start. |
| `PDF_EDITOR_CORS_ORIGINS` | Backend | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173` | Comma-separated list of allowed browser origins. Set this to your deployed frontend origin. |

`PDF_EDITOR_CORS_ORIGINS` is read from the process environment. You can also pass it to Uvicorn with `--env-file`:

```bash
uvicorn app.main:app --env-file .env --port 8000
```

A `backend/.env.example` is provided for that purpose.

### Current limits

- Maximum upload size: 80 MB.
- Maximum fields per save: 3,000.
- Unsupported input: encrypted PDFs, non-PDF files, and PDFs without pages.
- Image fields accept PNG and JPEG data URLs up to 8 MB.

## Using the editor

1. Click **Open PDF** and choose a document. The file is uploaded to the local backend and rendered in the browser.
2. Review detected fields in the sidebar and on the page. Each field shows its label and confidence in the properties panel.
3. Double-click a field to type; click a checkbox or radio option to toggle it.
4. Draw missing fields with the toolbar, then adjust them in the properties panel.
5. Click **Save PDF** to download a copy with real widgets, or **Flatten copy** to bake values into the page.
6. Use **Open saved copy** to reopen the generated file and confirm that fields and values survived the round trip.

The source file on disk is never overwritten. Saved copies are named from the source document and downloaded by the browser.

### Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl/Cmd+Z` | Undo |
| `Ctrl/Cmd+Shift+Z`, `Ctrl/Cmd+Y` | Redo |
| `Delete`, `Backspace` | Delete selected field |
| Arrow keys | Move selected field by 1 pt |
| `Shift` + arrow keys | Move selected field by 10 pt |
| `Escape` | Cancel editing, deselect, return to Select tool |
| `Enter` | Commit a single-line field |
| `Ctrl/Cmd+Enter` | Commit a multiline field |

## Tests

Backend:

```bash
cd backend
python -m pytest -q
```

The public test suite covers widget creation and verification, checked-state round trips, image embedding and rejection, flattening, detection heuristics, document validation, generic template application, and the HTTP API. It runs entirely from synthetic fixtures; no private form or bundled third-party template is required. Local template-validation tests run only when a local template is present.

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

The build step runs TypeScript project checks before producing `frontend/dist/`.

`frontend/tools/drive-ui.mjs` is a generic Playwright acceptance driver. With the servers running, pass any PDF and it uploads the document, waits for detected fields, saves a copy, reopens it, and checks that the fields survived:

```bash
cd frontend
node tools/drive-ui.mjs /path/to/form.pdf
```

Set `DRIVE_FIELD_TITLE` and `DRIVE_VALUE` to edit a named field before saving. The driver is a development tool, not part of the default test command.

## Production build

```bash
cd frontend
npm ci
VITE_API_BASE=https://pdf-api.example.com npm run build
```

Serve the contents of `frontend/dist/` with any static web server. The build is a single-page application, so route unknown paths to `index.html`.

Run the backend with one worker:

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**Use exactly one worker.** Document metadata and temporary-file registries live in process memory. Multiple workers would not see each other's documents and requests would fail with 404s. Scale only after replacing the in-memory store with shared storage.

Recommended deployment shape:

```text
Internet ── TLS ── reverse proxy (authentication, request limits)
                        ├── /            → frontend/dist/
                        └── /api/        → 127.0.0.1:8000
```

Set `PDF_EDITOR_CORS_ORIGINS` to the public frontend origin. Because the app has no accounts or per-user authorization, do not expose it directly to the public internet. If you operate a modified version over a network, AGPL section 13 requires that users be offered the corresponding source code.

## Known limitations

- Single-user, single-process design; no authentication, accounts, or tenant isolation.
- Documents live in the OS temporary directory. Metadata is in memory, so restarting the backend forgets documents, and abrupt termination can leave temporary files behind.
- No automatic expiry or orphan cleanup of temporary files yet.
- Detection is geometric and text-based. Scanned, image-only PDFs need manual authoring (or OCR before upload); XFA forms and encrypted PDFs are not supported.
- Detection results are proposals. Always review field positions and types, especially on pages with unusual layouts or rotation.
- Signature fields are empty AcroForm signature widgets. Signing must happen in a PDF application that supports digital signatures.
- Image values are embedded as page content behind a transparent placeholder widget. This is intentional so photos stay visible after flattening, but it is not reversible by deleting the widget.
- Text fields use Helvetica. Fonts are not copied from the source document.
- Templates are local, form-specific files. No template is distributed with the repository, and a template is not portable between differently laid-out documents.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. Please report security issues privately as described in [SECURITY.md](SECURITY.md).

## License

This project is licensed under the **GNU Affero General Public License v3.0 only** (`AGPL-3.0-only`). See [LICENSE](LICENSE).

PyMuPDF, the PDF engine behind the backend, is dual-licensed under AGPL-3.0 or a commercial license from Artifex. Using this project under AGPL is compatible with the AGPL path. If AGPL is not acceptable for your organization, obtain a commercial PyMuPDF license and review this project's licensing accordingly.

Copyright (C) 2026 PDF Form Editor contributors.
