import { useRef, useState } from "react";
import type { Field, Rect } from "../types";
import { fitFontSize } from "../coordinates";

interface Props {
  field: Field;
  css: { left: number; top: number; width: number; height: number };
  scale: number;
  selected: boolean;
  editing: boolean;
  interactive: boolean;
  pageWidth: number;
  pageHeight: number;
  toCanonical: (clientX: number, clientY: number) => [number, number];
  toCss: (rect: Rect) => { left: number; top: number; width: number; height: number };
  onSelect: (id: string) => void;
  onEdit: (id: string) => void;
  onCommit: (id: string, patch: Partial<Field>) => void;
  onToggle: (field: Field) => void;
}

const HANDLES = ["nw", "n", "ne", "e", "se", "s", "sw", "w"] as const;
type Handle = (typeof HANDLES)[number];

const MIN_SIZE = 5;

function clamp(value: number, low: number, high: number): number {
  return Math.max(low, Math.min(high, value));
}

function resizeRect(rect: Rect, handle: Handle, dx: number, dy: number, pageWidth: number, pageHeight: number): Rect {
  const [x0, y0, x1, y1] = rect;
  let left = x0;
  let top = y0;
  let right = x1;
  let bottom = y1;
  if (handle.includes("w")) left = clamp(x0 + dx, 0, x1 - MIN_SIZE);
  if (handle.includes("e")) right = clamp(x1 + dx, x0 + MIN_SIZE, pageWidth);
  if (handle.includes("n")) top = clamp(y0 + dy, 0, y1 - MIN_SIZE);
  if (handle.includes("s")) bottom = clamp(y1 + dy, y0 + MIN_SIZE, pageHeight);
  return [left, top, right, bottom];
}

export function FieldBox({
  field,
  css,
  scale,
  selected,
  editing,
  interactive,
  pageWidth,
  pageHeight,
  toCanonical,
  toCss,
  onSelect,
  onEdit,
  onCommit,
  onToggle,
}: Props) {
  const [preview, setPreview] = useState<Rect | null>(null);
  const dragStart = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const resizeStart = useRef<{ handle: Handle; x: number; y: number; rect: Rect } | null>(null);

  const beginDrag = (event: React.PointerEvent) => {
    if (!interactive || event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.dataset.handle) return;
    event.stopPropagation();
    onSelect(field.id);
    const [x, y] = toCanonical(event.clientX, event.clientY);
    dragStart.current = { x, y, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const beginResize = (handle: Handle, event: React.PointerEvent) => {
    if (!interactive || event.button !== 0) return;
    event.stopPropagation();
    event.preventDefault();
    onSelect(field.id);
    const [x, y] = toCanonical(event.clientX, event.clientY);
    resizeStart.current = { handle, x, y, rect: [...field.rect] };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const move = (event: React.PointerEvent) => {
    const resize = resizeStart.current;
    if (resize) {
      const [x, y] = toCanonical(event.clientX, event.clientY);
      setPreview(resizeRect(resize.rect, resize.handle, x - resize.x, y - resize.y, pageWidth, pageHeight));
      return;
    }
    const start = dragStart.current;
    if (!start) return;
    const [x, y] = toCanonical(event.clientX, event.clientY);
    const dx = x - start.x;
    const dy = y - start.y;
    if (Math.abs(dx) > 0.6 || Math.abs(dy) > 0.6) start.moved = true;
    const [x0, y0, x1, y1] = field.rect;
    const width = x1 - x0;
    const height = y1 - y0;
    const left = clamp(x0 + dx, 0, pageWidth - width);
    const top = clamp(y0 + dy, 0, pageHeight - height);
    setPreview([left, top, left + width, top + height]);
  };

  const end = (event: React.PointerEvent) => {
    const resize = resizeStart.current;
    if (resize) {
      resizeStart.current = null;
      const [x, y] = toCanonical(event.clientX, event.clientY);
      const rect = resizeRect(resize.rect, resize.handle, x - resize.x, y - resize.y, pageWidth, pageHeight);
      setPreview(null);
      if (rect.some((value, index) => Math.abs(value - resize.rect[index]) > 0.05)) {
        onCommit(field.id, { rect });
      }
      return;
    }

    const start = dragStart.current;
    dragStart.current = null;
    const rect = preview;
    setPreview(null);
    if (!start) return;
    if (!start.moved) {
      if (field.type === "checkbox" || field.type === "radio") onToggle(field);
      return;
    }
    if (rect) {
      const [x0, y0, x1, y1] = field.rect;
      if (rect.some((value, index) => Math.abs(value - [x0, y0, x1, y1][index]) > 0.05)) {
        onCommit(field.id, { rect });
      }
    }
  };

  const heightPt = field.rect[3] - field.rect[1];
  const fontSize = (field.fontSize > 0 ? field.fontSize : fitFontSize(heightPt)) * scale;
  const value = typeof field.value === "string" ? field.value : "";
  const isCheck = field.type === "checkbox" || field.type === "radio";
  const isImage = field.type === "image" && value.startsWith("data:image");
  const box = preview ? toCss(preview) : css;

  return (
    <div
      className={`field-box field-${field.type}${selected ? " is-selected" : ""}${editing ? " is-editing" : ""}`}
      data-field-id={field.id}
      style={{ left: box.left, top: box.top, width: box.width, height: box.height }}
      title={field.label || field.name}
      onPointerDown={beginDrag}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
      onDoubleClick={(event) => {
        if (!interactive || isCheck) return;
        event.stopPropagation();
        onEdit(field.id);
      }}
    >
      {!editing && isCheck && (
        <span className="field-check" style={{ fontSize: Math.max(7, css.height * 0.92) }} aria-hidden>
          {field.checked ? (field.type === "radio" ? "●" : "✓") : ""}
        </span>
      )}

      {!editing && !isCheck && isImage && <img src={value} alt={field.label} draggable={false} />}

      {!editing && !isCheck && !isImage && value && (
        <span
          className="field-text"
          style={{ fontSize, textAlign: field.alignment, lineHeight: `${Math.max(fontSize * 1.05, fontSize + 2)}px` }}
        >
          {value}
        </span>
      )}

      {!editing && !isCheck && !isImage && !value && field.type === "dropdown" && (
        <span className="field-caret">▾</span>
      )}

      {selected && interactive && (
        <span className="resize-handles" aria-hidden>
          {HANDLES.map((handle) => (
            <span
              key={handle}
              className={`handle handle-${handle}`}
              data-handle={handle}
              onPointerDown={(event) => beginResize(handle, event)}
            />
          ))}
        </span>
      )}
    </div>
  );
}
