# Contributing

Thanks for taking the time to improve PDF Form Editor. This project handles documents that may contain personal data, so correctness and privacy take priority over speed.

## Before you start

- Search existing issues and pull requests.
- For a bug, include the smallest synthetic PDF that reproduces it. Never upload a real application form, passport, identity document, or anything containing personal data.
- For a large feature or a change to the field model, open an issue first so the design can be discussed.
- Report security problems privately as described in [SECURITY.md](SECURITY.md).

## Development setup

Follow the installation steps in the [README](README.md). In short:

```bash
# Backend
python -m venv backend/.venv
source backend/.venv/bin/activate        # Windows: backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

# Frontend
cd frontend
npm ci
```

Run the backend from `backend/` and the frontend from `frontend/`:

```bash
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## Checks before opening a pull request

```bash
cd backend && python -m pytest -q
cd frontend && npm run lint && npm run build
```

Tests that require the private bank form are skipped automatically when it is absent. Add unit tests for detection, widget creation, or geometry changes; do not rely on manual testing alone.

If you change the UI, exercise the real application in a browser. `frontend/tools/drive-ui.mjs` is a generic acceptance driver: pass any PDF path and it uploads, saves, and reopens the document. It is not part of the default test command.

## Project conventions

### Coordinates

Field rectangles are always `[x0, y0, x1, y1]` in PDF points, in the unrotated crop-box space, with the origin at the top-left and y increasing downward.

- Do not store pixels, CSS units, zoom-scaled values, or viewport coordinates in a field.
- Convert through the PDF.js viewport (`frontend/src/coordinates.ts`) and nowhere else.
- The backend must not apply a second conversion. PyMuPDF uses the same canonical space.
- A change is incomplete if it breaks field positions across zoom, resize, save, or reopen.

### PDF output

- Never rasterize pages or rebuild them from screenshots.
- Never modify printed labels or page content to make a field fit.
- Prefer annotation widgets over page edits. User-supplied images are the documented exception: they are embedded as page content behind a transparent placeholder.
- Never silently overwrite the source document. Save to a new output file and report what was written.
- Keep the post-save verification: every expected widget must be found on the expected page within tolerance.

### Detection

Detection proposes fields and must stay conservative:

- Do not emit a field without a label, placeholder, or geometric evidence.
- Do not mark declarations, instructions, or fixed printed text as editable.
- Preserve the confidence value and evidence used to propose a field.
- Add a targeted test for any new heuristic and for the false positive it is meant to avoid.

### Code

- Python: keep type hints on public functions, prefer small functions, and use `pymupdf` APIs rather than shelling out.
- TypeScript: avoid `any`; keep geometry math in the coordinate module; keep components free of network side effects where possible.
- Match the existing formatting and naming. Do not add unrelated refactors to a bug-fix pull request.
- Do not add telemetry, analytics, remote logging, external AI calls, or document uploads to third parties.

### Templates

Templates are optional local JSON files in `backend/app/templates/`, and each one pins rectangles to a specific form layout. The public repository does not ship any template. If you propose bundling one, confirm its redistribution rights and the source form's rights first; never include the source form PDF in the repository. The public test suite validates the template schema and application logic with synthetic data, so it does not depend on a bundled template.

## Commit messages

Use a short imperative summary, for example:

```text
Fix checkbox state after reopening a saved form
Add regression test for multiline field geometry
```

Keep the body focused on why the change is needed. If a fix changes PDF output, describe how it was verified.

## Pull request checklist

- [ ] The change is scoped to one problem.
- [ ] Backend tests pass; new behaviour has tests.
- [ ] `npm run lint` and `npm run build` pass for frontend changes.
- [ ] Field positions were checked after save and reopen, not only in the editor.
- [ ] No PDFs, personal data, secrets, local paths, or generated files are included.
- [ ] Documentation is updated when configuration, limits, or behaviour changes.
- [ ] New dependencies are necessary and license-compatible with AGPL-3.0.

## Licensing of contributions

By submitting a contribution you agree that it is licensed under the project's `AGPL-3.0-only` license. No contributor license agreement is required. Do not copy code from projects whose licenses are incompatible with AGPL-3.0.
