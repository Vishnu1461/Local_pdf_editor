import type { Field, FieldType } from "../types";

const TYPES: FieldType[] = [
  "text",
  "multiline",
  "address",
  "date",
  "number",
  "email",
  "checkbox",
  "radio",
  "dropdown",
  "signature",
  "image",
];

interface Props {
  field: Field;
  onPatch: (id: string, patch: Partial<Field>) => void;
  onDelete: (id: string) => void;
}

export function PropertiesPanel({ field, onPatch, onDelete }: Props) {
  const update = (patch: Partial<Field>) => onPatch(field.id, patch);
  const width = (field.rect[2] - field.rect[0]).toFixed(1);
  const height = (field.rect[3] - field.rect[1]).toFixed(1);

  const sourceLabel =
    field.source === "template"
      ? "Template"
      : field.source === "existing"
        ? "Existing field"
        : field.source === "detected"
          ? `Detected · ${Math.round(field.confidence * 100)}%`
          : "Added by you";

  return (
    <aside className="props">
      <div className="props-head">
        <h2>Field</h2>
        <span className={`source-tag source-${field.source}`}>{sourceLabel}</span>
      </div>

      <label className="prop">
        <span>Label</span>
        <input value={field.label} onChange={(event) => update({ label: event.target.value })} />
      </label>

      <label className="prop">
        <span>Name</span>
        <input value={field.name} onChange={(event) => update({ name: event.target.value })} spellCheck={false} />
      </label>

      <label className="prop">
        <span>Type</span>
        <select value={field.type} onChange={(event) => update({ type: event.target.value as FieldType })}>
          {TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </label>

      {(field.type === "dropdown" || field.type === "radio") && (
        <label className="prop">
          <span>{field.type === "radio" ? "Group" : "Options"}</span>
          {field.type === "radio" ? (
            <input
              value={field.group ?? ""}
              placeholder={field.name}
              onChange={(event) => update({ group: event.target.value || null })}
            />
          ) : (
            <textarea
              rows={3}
              value={field.options.join("\n")}
              placeholder={"One option per line"}
              onChange={(event) =>
                update({ options: event.target.value.split("\n").map((line) => line.trim()).filter(Boolean) })
              }
            />
          )}
        </label>
      )}

      <div className="prop-row">
        <label className="prop">
          <span>Font size (0 = auto)</span>
          <input
            type="number"
            min={0}
            max={72}
            step={0.5}
            value={field.fontSize}
            onChange={(event) => update({ fontSize: Math.max(0, Number(event.target.value) || 0) })}
          />
        </label>
        <label className="prop">
          <span>Max chars</span>
          <input
            type="number"
            min={0}
            placeholder="none"
            value={field.maxLength ?? ""}
            onChange={(event) => {
              const raw = event.target.value;
              update({ maxLength: raw === "" ? null : Math.max(1, Number(raw)) });
            }}
          />
        </label>
      </div>

      <label className="prop">
        <span>Alignment</span>
        <select
          value={field.alignment}
          onChange={(event) => update({ alignment: event.target.value as Field["alignment"] })}
        >
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </select>
      </label>

      <label className="prop">
        <span>Background</span>
        <select
          value={field.background}
          onChange={(event) => update({ background: event.target.value as Field["background"] })}
        >
          <option value="white">White fill</option>
          <option value="none">Transparent</option>
        </select>
      </label>

      <label className="prop prop-inline">
        <input
          type="checkbox"
          checked={field.required}
          onChange={(event) => update({ required: event.target.checked })}
        />
        <span>Required</span>
      </label>

      {field.type === "image" && (
        <div className="prop">
          <span>Image</span>
          <input
            type="file"
            accept="image/png,image/jpeg"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              const reader = new FileReader();
              reader.onload = () => update({ value: String(reader.result) });
              reader.readAsDataURL(file);
            }}
          />
          {typeof field.value === "string" && field.value.startsWith("data:image") && (
            <img className="prop-preview" src={field.value} alt={field.label} />
          )}
        </div>
      )}

      {field.type === "signature" && (
        <p className="prop-note">Signature fields are signed inside Adobe Acrobat or another PDF reader.</p>
      )}

      <div className="prop-geometry">
        Page {field.page + 1} · x {field.rect[0].toFixed(1)}, y {field.rect[1].toFixed(1)} · {width} × {height} pt
      </div>

      <button className="danger" onClick={() => onDelete(field.id)}>
        Delete field
      </button>
    </aside>
  );
}
