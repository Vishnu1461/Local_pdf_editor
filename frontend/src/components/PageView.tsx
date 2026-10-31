import { useEffect, useRef, useState } from "react";
import { TextLayer, type PDFPageProxy, type PageViewport } from "pdfjs-dist";
import type { Field, PageInfo, Rect } from "../types";
import { canonicalToCssRect, cssPointToCanonical } from "../coordinates";
import { FieldBox } from "./FieldBox";
import { InlineEditor } from "./InlineEditor";

export type Tool = "select" | Field["type"];

interface Props {
  pdfPage: PDFPageProxy;
  pageInfo: PageInfo;
  scale: number;
  fields: Field[];
  selectedId: string | null;
  editingId: string | null;
  tool: Tool;
  onSelect: (id: string | null) => void;
  onEdit: (id: string) => void;
  onCommitValue: (id: string, value: string) => void;
  onCancelEdit: () => void;
  onToggle: (field: Field) => void;
  onPatch: (id: string, patch: Partial<Field>) => void;
  onCreate: (page: number, rect: Rect) => void;
}

export function PageView({
  pdfPage,
  pageInfo,
  scale,
  fields,
  selectedId,
  editingId,
  tool,
  onSelect,
  onEdit,
  onCommitValue,
  onCancelEdit,
  onToggle,
  onPatch,
  onCreate,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState<PageViewport | null>(null);
  const drawStart = useRef<[number, number] | null>(null);
  const [drawRect, setDrawRect] = useState<{ left: number; top: number; width: number; height: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const view = pdfPage.getViewport({ scale });
    setViewport(view);
    const context = canvas.getContext("2d");
    if (!context) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(view.width * dpr);
    canvas.height = Math.floor(view.height * dpr);
    canvas.style.width = `${view.width}px`;
    canvas.style.height = `${view.height}px`;

    let cancelled = false;
    const task = pdfPage.render({
      canvasContext: context,
      canvas,
      viewport: view,
      transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
      // Widgets are drawn by the app's own field layer; painting their
      // appearances here would double values and hide printed hints.
      annotationMode: 0,
    });

    task.promise
      .then(async () => {
        if (cancelled) return;
        const container = textRef.current;
        if (!container) return;
        container.replaceChildren();
        const content = await pdfPage.getTextContent();
        if (cancelled) return;
        const layer = new TextLayer({ textContentSource: content, container, viewport: view });
        await layer.render();
      })
      .catch((error: unknown) => {
        if ((error as { name?: string })?.name !== "RenderingCancelledException") {
          console.error("page render failed", error);
        }
      });

    return () => {
      cancelled = true;
      task.cancel();
    };
  }, [pdfPage, scale]);

  const viewBox = pdfPage.view as [number, number, number, number];

  const toCanonical = (clientX: number, clientY: number): [number, number] => {
    if (!viewport) return [0, 0];
    const bounds = wrapperRef.current?.getBoundingClientRect();
    if (!bounds) return [0, 0];
    return cssPointToCanonical(clientX - bounds.left, clientY - bounds.top, viewport, viewBox);
  };

  const toCss = (rect: Rect) => {
    if (!viewport) return { left: 0, top: 0, width: 0, height: 0 };
    return canonicalToCssRect(rect, viewport, viewBox);
  };

  const beginDraw = (event: React.PointerEvent) => {
    if (tool === "select" || !viewport || event.button !== 0) return;
    event.preventDefault();
    const [x, y] = toCanonical(event.clientX, event.clientY);
    drawStart.current = [x, y];
    setDrawRect({ ...toCss([x, y, x + 0.01, y + 0.01]) });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const updateDraw = (event: React.PointerEvent) => {
    const start = drawStart.current;
    if (!start) return;
    const [x, y] = toCanonical(event.clientX, event.clientY);
    const rect: Rect = [Math.min(start[0], x), Math.min(start[1], y), Math.max(start[0], x), Math.max(start[1], y)];
    setDrawRect(toCss(rect));
  };

  const endDraw = (event: React.PointerEvent) => {
    const start = drawStart.current;
    drawStart.current = null;
    setDrawRect(null);
    if (!start) return;
    const [x, y] = toCanonical(event.clientX, event.clientY);
    const rect: Rect = [Math.min(start[0], x), Math.min(start[1], y), Math.max(start[0], x), Math.max(start[1], y)];
    if (rect[2] - rect[0] < 4 || rect[3] - rect[1] < 4) {
      onSelect(null);
      return;
    }
    onCreate(pageInfo.index, rect);
  };

  const editing = fields.find((field) => field.id === editingId) ?? null;
  const editorCss = editing ? toCss(editing.rect) : null;

  return (
    <div
      ref={wrapperRef}
      className={`page${tool === "select" ? "" : " is-drawing"}`}
      style={{ width: viewport?.width ?? pageInfo.width * scale, height: viewport?.height ?? pageInfo.height * scale }}
      data-page={pageInfo.index}
      onPointerDown={(event) => {
        if (tool !== "select") return;
        if ((event.target as HTMLElement).closest(".field-box")) return;
        onSelect(null);
      }}
    >
      <canvas ref={canvasRef} className="page-canvas" />
      <div
        ref={textRef}
        className="textLayer"
        style={{ "--total-scale-factor": viewport?.scale ?? scale } as React.CSSProperties}
      />

      <div
        className="field-layer"
        onPointerDown={beginDraw}
        onPointerMove={updateDraw}
        onPointerUp={endDraw}
        onPointerCancel={endDraw}
      >
        {drawRect && <div className="draw-rect" style={drawRect} />}
      </div>

      <div className="fields-layer">
        {viewport &&
          fields.map((field) => (
            <FieldBox
              key={field.id}
              field={field}
              css={canonicalToCssRect(field.rect, viewport, viewBox)}
              scale={viewport.scale}
              selected={field.id === selectedId}
              editing={field.id === editingId}
              interactive={tool === "select"}
              pageWidth={pageInfo.width}
              pageHeight={pageInfo.height}
              toCanonical={toCanonical}
              toCss={toCss}
              onSelect={(id) => onSelect(id)}
              onEdit={onEdit}
              onCommit={onPatch}
              onToggle={onToggle}
            />
          ))}
      </div>

      {editing && editorCss && (
        <InlineEditor
          field={editing}
          css={editorCss}
          scale={viewport?.scale ?? scale}
          onCommit={(value) => onCommitValue(editing.id, value)}
          onCancel={onCancelEdit}
        />
      )}
    </div>
  );
}
