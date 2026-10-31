import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Field } from "../types";
import { fitFontSize } from "../coordinates";

interface Props {
  field: Field;
  css: { left: number; top: number; width: number; height: number };
  scale: number;
  onCommit: (value: string) => void;
  onCancel: () => void;
}

/**
 * Inline editor: sits exactly on the printed blank, uses the field's point
 * size scaled to the current zoom, and shrinks the text until it fits the
 * field instead of overflowing or changing the layout.
 */
export function InlineEditor({ field, css, scale, onCommit, onCancel }: Props) {
  const multiline = field.type === "multiline" || field.type === "address";
  const initial = typeof field.value === "string" ? field.value : "";
  const [value, setValue] = useState(initial);
  const [fontSize, setFontSize] = useState(
    Math.max(5, (field.fontSize > 0 ? field.fontSize : fitFontSize(field.rect[3] - field.rect[1])) * scale),
  );
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  const finished = useRef(false);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    el.select();
  }, []);

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    const maxSize = Math.max(5, (field.fontSize > 0 ? field.fontSize : fitFontSize(field.rect[3] - field.rect[1])) * scale);
    let size = maxSize;
    el.style.fontSize = `${size}px`;
    if (multiline) {
      while (el.scrollHeight > el.clientHeight + 1 && size > 5) {
        size -= 0.5;
        el.style.fontSize = `${size}px`;
      }
    } else {
      while (el.scrollWidth > el.clientWidth + 1 && size > 5) {
        size -= 0.5;
        el.style.fontSize = `${size}px`;
      }
    }
    setFontSize(size);
  }, [value, multiline, scale, field.fontSize, field.rect]);

  const commit = () => {
    if (finished.current) return;
    finished.current = true;
    onCommit(value);
  };
  const cancel = () => {
    if (finished.current) return;
    finished.current = true;
    onCancel();
  };

  const style: React.CSSProperties = {
    left: css.left,
    top: css.top,
    width: css.width,
    height: css.height,
    fontSize,
    textAlign: field.alignment,
    fontFamily: "Helvetica, Arial, sans-serif",
  };

  const common = {
    value,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const next = e.target.value;
      setValue(field.maxLength ? next.slice(0, field.maxLength) : next);
    },
    onBlur: commit,
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        cancel();
        return;
      }
      if (e.key === "Enter" && (!multiline || e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        commit();
      }
    },
    className: "inline-editor",
    style,
    spellCheck: false,
  };

  return multiline ? (
    <textarea
      ref={inputRef as React.RefObject<HTMLTextAreaElement>}
      {...common}
      rows={1}
    />
  ) : (
    <input
      ref={inputRef as React.RefObject<HTMLInputElement>}
      {...common}
      type="text"
      inputMode={field.type === "number" ? "numeric" : undefined}
      placeholder=""
    />
  );
}
