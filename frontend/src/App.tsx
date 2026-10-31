import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentLoadingTask,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  applyTemplate,
  detectFields,
  downloadOutput,
  listTemplates,
  saveDocument,
  sourceUrl,
  uploadDocument,
} from "./api";
import { fitFontSize } from "./coordinates";
import { useHistory } from "./history";
import type { DocumentInfo, Field, Rect, SaveReport, TemplateSummary } from "./types";
import { PageView, type Tool } from "./components/PageView";
import { Sidebar } from "./components/Sidebar";
import { PropertiesPanel } from "./components/PropertiesPanel";

GlobalWorkerOptions.workerSrc = workerUrl;

const TOOLS: { id: Tool; label: string }[] = [
  { id: "select", label: "Select" },
  { id: "text", label: "Text" },
  { id: "multiline", label: "Paragraph" },
  { id: "date", label: "Date" },
  { id: "number", label: "Number" },
  { id: "email", label: "Email" },
  { id: "checkbox", label: "Checkbox" },
  { id: "radio", label: "Radio" },
  { id: "dropdown", label: "Dropdown" },
  { id: "signature", label: "Signature" },
  { id: "image", label: "Image" },
];

const CHECK_TYPES = new Set(["checkbox", "radio", "dropdown", "signature"]);

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function uniqueName(base: string, used: Set<string>): string {
  let name = base;
  let index = 2;
  while (used.has(name)) {
    name = `${base}_${index}`;
    index += 1;
  }
  return name;
}

function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

export default function App() {
  const [docInfo, setDocInfo] = useState<DocumentInfo | null>(null);
  const [pdf, setPdf] = useState<PDFDocumentProxy | null>(null);
  const [pages, setPages] = useState<PDFPageProxy[]>([]);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [scale, setScale] = useState(1.2);
  const [fitMode, setFitMode] = useState<"width" | "page" | "custom">("width");
  const [currentPage, setCurrentPage] = useState(0);
  const [saving, setSaving] = useState<"save" | "flatten" | null>(null);
  const [report, setReport] = useState<SaveReport | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [areaSize, setAreaSize] = useState({ width: 0, height: 0 });

  const history = useHistory<Field[]>([]);
  const fields = history.value;
  const viewerRef = useRef<HTMLElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const loadingTaskRef = useRef<PDFDocumentLoadingTask | null>(null);

  const selectedField = useMemo(
    () => fields.find((field) => field.id === selectedId) ?? null,
    [fields, selectedId],
  );

  const templateName = useMemo(() => {
    if (!docInfo?.templateMatch) return null;
    return templates.find((template) => template.id === docInfo.templateMatch)?.name ?? docInfo.templateMatch;
  }, [docInfo, templates]);

  const commitFields = useCallback(
    (next: Field[]) => {
      history.commit(next);
      setDirty(true);
    },
    [history],
  );

  useEffect(() => {
    listTemplates().then(setTemplates).catch(() => undefined);
  }, []);

  useEffect(() => {
    const element = viewerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      setAreaSize({ width: element.clientWidth, height: element.clientHeight });
    });
    observer.observe(element);
    setAreaSize({ width: element.clientWidth, height: element.clientHeight });
    return () => observer.disconnect();
  }, [docInfo]);

  useEffect(() => {
    if (!docInfo || !areaSize.width) return;
    const maxWidth = Math.max(...docInfo.pages.map((page) => page.width));
    const maxHeight = Math.max(...docInfo.pages.map((page) => page.height));
    if (fitMode === "width") {
      setScale(clamp((areaSize.width - 80) / maxWidth, 0.3, 4));
    } else if (fitMode === "page") {
      setScale(
        clamp(
          Math.min((areaSize.width - 80) / maxWidth, (areaSize.height - 80) / maxHeight),
          0.2,
          4,
        ),
      );
    }
  }, [fitMode, areaSize, docInfo]);

  useEffect(() => {
    if (!docInfo) {
      setPdf(null);
      setPages([]);
      return;
    }
    let cancelled = false;
    let loaded: PDFDocumentProxy | null = null;
    (async () => {
      const response = await fetch(sourceUrl(docInfo.id));
      if (!response.ok) throw new Error("could not load the PDF from the local server");
      const data = new Uint8Array(await response.arrayBuffer());
      loadingTaskRef.current?.destroy();
      const task = getDocument({ data });
      loadingTaskRef.current = task;
      loaded = await task.promise;
      if (cancelled) {
        await task.destroy();
        return;
      }
      setPdf(loaded);
    })().catch((cause: unknown) => {
      if (!cancelled) setError(errorMessage(cause));
    });
    return () => {
      cancelled = true;
    };
  }, [docInfo]);

  useEffect(() => {
    if (!pdf) {
      setPages([]);
      return;
    }
    let cancelled = false;
    Promise.all(Array.from({ length: pdf.numPages }, (_, index) => pdf.getPage(index + 1)))
      .then((list) => {
        if (!cancelled) setPages(list);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(errorMessage(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [pdf]);

  useEffect(
    () => () => {
      void loadingTaskRef.current?.destroy();
    },
    [],
  );

  const openFile = useCallback(
    async (file: File, options: { autoTemplate: boolean } = { autoTemplate: true }) => {
      setLoading(true);
      setError(null);
      setReport(null);
      setStatus(null);
      try {
        const info = await uploadDocument(file);
        let initial: Field[] = info.fields;
        let note = `${info.pageCount} pages loaded`;
        if (initial.length === 0 && info.templateMatch && options.autoTemplate) {
          initial = await applyTemplate(info.id, info.templateMatch);
          note = `Applied the ${info.templateMatch} template (${initial.length} fields)`;
        } else if (initial.length === 0 && options.autoTemplate) {
          const detected = await detectFields(info.id);
          initial = detected.fields;
          note = `Detected ${initial.length} blank areas`;
        } else if (initial.length > 0) {
          note = `Loaded ${initial.length} existing form fields`;
        }
        setDocInfo(info);
        history.reset(initial);
        setSelectedId(null);
        setEditingId(null);
        setTool("select");
        setCurrentPage(0);
        setFitMode("width");
        setDirty(false);
        setStatus(note);
      } catch (cause) {
        setError(errorMessage(cause));
      } finally {
        setLoading(false);
      }
    },
    [history],
  );

  const runDetection = useCallback(async () => {
    if (!docInfo) return;
    if (fields.length > 0 && !window.confirm("Replace the current fields with fresh detection results?")) {
      return;
    }
    setDetecting(true);
    setError(null);
    try {
      const detected = await detectFields(docInfo.id);
      history.commit(detected.fields);
      setSelectedId(null);
      setEditingId(null);
      setDirty(true);
      setStatus(`Detected ${detected.fields.length} blank areas`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setDetecting(false);
    }
  }, [docInfo, fields.length, history]);

  const patchField = useCallback(
    (id: string, patch: Partial<Field>) => {
      commitFields(fields.map((field) => (field.id === id ? { ...field, ...patch } : field)));
    },
    [commitFields, fields],
  );

  const toggleField = useCallback(
    (field: Field) => {
      if (field.type === "radio") {
        const group = field.group || field.name;
        commitFields(
          fields.map((candidate) =>
            candidate.type === "radio" && (candidate.group || candidate.name) === group
              ? { ...candidate, checked: candidate.id === field.id }
              : candidate,
          ),
        );
        return;
      }
      patchField(field.id, { checked: !field.checked });
    },
    [commitFields, fields, patchField],
  );

  const createField = useCallback(
    (page: number, rect: Rect) => {
      if (!docInfo) return;
      const type: Field["type"] = tool === "select" ? "text" : tool;
      const used = new Set(fields.map((field) => field.name));
      const pageInfo = docInfo.pages[page];
      const clipped: Rect = [
        clamp(rect[0], 0, pageInfo.width),
        clamp(rect[1], 0, pageInfo.height),
        clamp(rect[2], 0, pageInfo.width),
        clamp(rect[3], 0, pageInfo.height),
      ];
      const height = clipped[3] - clipped[1];
      const field: Field = {
        id: crypto.randomUUID(),
        page,
        rect: clipped,
        type,
        name: uniqueName(slug(type), used),
        label: `Field ${fields.length + 1}`,
        value: null,
        checked: false,
        background: type === "image" || type === "checkbox" || type === "radio" ? "none" : "white",
        required: false,
        fontSize: CHECK_TYPES.has(type) ? 0 : fitFontSize(height),
        alignment: "left",
        maxLength: type === "date" ? 10 : null,
        options: type === "dropdown" ? ["Option 1", "Option 2"] : [],
        group: type === "radio" ? uniqueName("choice", new Set(fields.map((item) => item.group ?? ""))) : null,
        confidence: 1,
        source: "manual",
        tooltip: "",
      };
      commitFields([...fields, field]);
      setSelectedId(field.id);
      setTool("select");
    },
    [commitFields, docInfo, fields, tool],
  );

  const removeField = useCallback(
    (id: string) => {
      commitFields(fields.filter((field) => field.id !== id));
      setSelectedId((current) => (current === id ? null : current));
      setEditingId((current) => (current === id ? null : current));
    },
    [commitFields, fields],
  );

  const commitValue = useCallback(
    (id: string, value: string) => {
      patchField(id, { value });
      setEditingId(null);
    },
    [patchField],
  );

  const nudgeSelected = useCallback(
    (dx: number, dy: number) => {
      if (!selectedField || !docInfo) return;
      const page = docInfo.pages[selectedField.page];
      const [x0, y0, x1, y1] = selectedField.rect;
      const width = x1 - x0;
      const height = y1 - y0;
      const left = clamp(x0 + dx, 0, page.width - width);
      const top = clamp(y0 + dy, 0, page.height - height);
      patchField(selectedField.id, { rect: [left, top, left + width, top + height] });
    },
    [docInfo, patchField, selectedField],
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        Boolean(target?.isContentEditable);

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !typing) {
        event.preventDefault();
        if (event.shiftKey) history.redo();
        else history.undo();
        setDirty(true);
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "y" && !typing) {
        event.preventDefault();
        history.redo();
        setDirty(true);
        return;
      }
      if (typing) return;

      if (event.key === "Escape") {
        setEditingId(null);
        setSelectedId(null);
        setTool("select");
        return;
      }
      if ((event.key === "Delete" || event.key === "Backspace") && selectedId) {
        event.preventDefault();
        removeField(selectedId);
        return;
      }
      if (event.key.startsWith("Arrow") && selectedId) {
        event.preventDefault();
        const step = event.shiftKey ? 10 : 1;
        if (event.key === "ArrowLeft") nudgeSelected(-step, 0);
        if (event.key === "ArrowRight") nudgeSelected(step, 0);
        if (event.key === "ArrowUp") nudgeSelected(0, -step);
        if (event.key === "ArrowDown") nudgeSelected(0, step);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [history, nudgeSelected, removeField, selectedId]);

  const handleSave = useCallback(
    async (flatten: boolean) => {
      if (!docInfo) return;
      setSaving(flatten ? "flatten" : "save");
      setError(null);
      try {
        const base = docInfo.name.replace(/\.pdf$/i, "");
        const fileName = `${base}-${flatten ? "flattened" : "filled"}.pdf`;
        const saved = await saveDocument(docInfo.id, fields, { flatten, fileName });
        const blob = await downloadOutput(saved);
        downloadBlob(blob, saved.fileName);
        setReport(saved);
        setDirty(false);
        setStatus(
          flatten
            ? `Flattened copy saved · ${saved.pageCount} pages`
            : `Saved ${saved.widgetCount} editable form fields`,
        );
      } catch (cause) {
        setError(errorMessage(cause));
      } finally {
        setSaving(null);
      }
    },
    [docInfo, fields],
  );

  const openSavedCopy = useCallback(async () => {
    if (!report) return;
    try {
      const blob = await downloadOutput(report);
      const file = new File([blob], report.fileName, { type: "application/pdf" });
      await openFile(file, { autoTemplate: false });
      setReport(null);
      setStatus("Opened the saved copy");
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }, [openFile, report]);

  const onScroll = useCallback(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const viewerBox = viewer.getBoundingClientRect();
    const target = viewerBox.top + 120;
    let best = 0;
    let bestDistance = Number.POSITIVE_INFINITY;
    viewer.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      const box = element.getBoundingClientRect();
      const distance = Math.abs(box.top - target);
      if (box.bottom > viewerBox.top && box.top < viewerBox.bottom && distance < bestDistance) {
        bestDistance = distance;
        best = Number(element.dataset.page ?? 0);
      }
    });
    setCurrentPage(best);
  }, []);

  const goPage = useCallback((index: number) => {
    const element = viewerRef.current?.querySelector<HTMLElement>(`[data-page="${index}"]`);
    element?.scrollIntoView({ block: "start" });
    setCurrentPage(index);
  }, []);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const field of fields) result[field.type] = (result[field.type] ?? 0) + 1;
    return result;
  }, [fields]);

  return (
    <div
      className="app"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file) void openFile(file);
      }}
    >
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◫</span> PDF Form Editor
        </div>

        <button className="primary" onClick={() => fileInputRef.current?.click()} disabled={loading}>
          {loading ? "Opening…" : "Open PDF"}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void openFile(file);
            event.target.value = "";
          }}
        />

        {docInfo && (
          <>
            <span className="divider" />
            <div className="zoom-group">
              <button onClick={() => { setFitMode("custom"); setScale((value) => clamp(value / 1.15, 0.25, 4)); }} title="Zoom out">
                −
              </button>
              <span className="zoom-value">{Math.round(scale * 100)}%</span>
              <button onClick={() => { setFitMode("custom"); setScale((value) => clamp(value * 1.15, 0.25, 4)); }} title="Zoom in">
                +
              </button>
              <button className={fitMode === "width" ? "active" : ""} onClick={() => setFitMode("width")}>
                Fit width
              </button>
              <button className={fitMode === "page" ? "active" : ""} onClick={() => setFitMode("page")}>
                Fit page
              </button>
            </div>

            <span className="divider" />
            <div className="pager">
              <button onClick={() => goPage(Math.max(0, currentPage - 1))} disabled={currentPage === 0}>
                ‹
              </button>
              <span>
                Page {currentPage + 1} / {docInfo.pageCount}
              </span>
              <button
                onClick={() => goPage(Math.min(docInfo.pageCount - 1, currentPage + 1))}
                disabled={currentPage === docInfo.pageCount - 1}
              >
                ›
              </button>
            </div>

            <span className="divider" />
            <button onClick={history.undo} disabled={!history.canUndo} title="Undo (Ctrl+Z)">
              Undo
            </button>
            <button onClick={history.redo} disabled={!history.canRedo} title="Redo (Ctrl+Shift+Z)">
              Redo
            </button>

            <div className="spacer" />

            <button onClick={() => void handleSave(false)} disabled={saving !== null} className="primary">
              {saving === "save" ? "Saving…" : "Save PDF"}
            </button>
            <button onClick={() => void handleSave(true)} disabled={saving !== null}>
              {saving === "flatten" ? "Saving…" : "Flatten copy"}
            </button>
          </>
        )}
      </header>

      {docInfo && (
        <div className="toolrow">
          {TOOLS.map((item) => (
            <button
              key={item.id}
              className={`tool${tool === item.id ? " active" : ""}`}
              onClick={() => setTool(item.id)}
              title={item.id === "select" ? "Select and edit fields" : `Draw a ${item.label.toLowerCase()} field`}
            >
              {item.label}
            </button>
          ))}
          <div className="spacer" />
          <button onClick={() => void runDetection()} disabled={detecting}>
            {detecting ? "Detecting…" : "Auto-detect blanks"}
          </button>
        </div>
      )}

      <div className="workspace">
        {docInfo && pdf && (
          <Sidebar
            pdf={pdf}
            pageCount={docInfo.pageCount}
            currentPage={currentPage}
            onGoPage={goPage}
            documentName={docInfo.name}
            fieldCount={fields.length}
            templateName={templateName}
          />
        )}

        <main className="viewer" ref={viewerRef} onScroll={onScroll}>
          {!docInfo && (
            <div className="empty">
              <div className="empty-card">
                <h1>Edit a PDF the way Acrobat does</h1>
                <p>
                  Open a form, double-click any blank area, and type. The original text, borders and layout stay untouched;
                  saving writes real AcroForm fields.
                </p>
                <button className="primary big" onClick={() => fileInputRef.current?.click()}>
                  Choose a PDF
                </button>
                <p className="empty-note">Or drop a PDF anywhere in this window.</p>
                <p className="empty-note">Everything runs locally — documents never leave this machine.</p>
              </div>
            </div>
          )}

          {docInfo && pdf && (
            <div className="pages">
              {pages.map((page, index) => (
                <PageView
                  key={index}
                  pdfPage={page}
                  pageInfo={docInfo.pages[index]}
                  scale={scale}
                  fields={fields.filter((field) => field.page === index)}
                  selectedId={selectedId}
                  editingId={editingId}
                  tool={tool}
                  onSelect={setSelectedId}
                  onEdit={setEditingId}
                  onCommitValue={commitValue}
                  onCancelEdit={() => setEditingId(null)}
                  onToggle={toggleField}
                  onPatch={patchField}
                  onCreate={createField}
                />
              ))}
            </div>
          )}
        </main>

        {selectedField ? (
          <PropertiesPanel field={selectedField} onPatch={patchField} onDelete={removeField} />
        ) : (
          docInfo && (
            <aside className="props">
              <div className="props-head">
                <h2>Document</h2>
              </div>
              <p className="prop-note">
                Double-click any blank area to type into it. Use the toolbar to draw a field where detection found
                nothing.
              </p>
              <div className="counts">
                {Object.entries(counts)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([type, count]) => (
                    <div key={type} className="count-row">
                      <span>{type}</span>
                      <strong>{count}</strong>
                    </div>
                  ))}
                <div className="count-row total">
                  <span>total</span>
                  <strong>{fields.length}</strong>
                </div>
              </div>
              {templateName && (
                <p className="prop-note">
                  Template: <strong>{templateName}</strong>
                </p>
              )}
              <p className="prop-note small">
                Uploads and saves stay in a private temporary folder on this machine. No document content is sent to an
                external service.
              </p>
            </aside>
          )
        )}
      </div>

      {report && (
        <div className="report">
          <div>
            <strong>{report.fileName}</strong> · {report.widgetCount} widgets ·{" "}
            {report.preservedPages ? "page geometry preserved" : "check warnings"}
            {report.warnings.length > 0 && <span className="warn"> · {report.warnings.length} warnings</span>}
          </div>
          <div className="report-actions">
            <button onClick={() => void openSavedCopy()}>Open saved copy</button>
            <button onClick={() => setReport(null)}>Dismiss</button>
          </div>
        </div>
      )}

      <footer className="statusbar">
        <span>{status ?? (docInfo ? (dirty ? "Unsaved changes" : "Ready") : "No document open")}</span>
        {docInfo && (
          <span className="status-right">
            {fields.length} fields · {docInfo.sha256.slice(0, 12)}
          </span>
        )}
      </footer>

      {error && (
        <div className="toast error" role="alert">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}
    </div>
  );
}
