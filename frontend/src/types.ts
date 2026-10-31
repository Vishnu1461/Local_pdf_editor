export type FieldType =
  | "text"
  | "multiline"
  | "date"
  | "number"
  | "email"
  | "address"
  | "checkbox"
  | "radio"
  | "dropdown"
  | "signature"
  | "image";

export type Rect = [number, number, number, number];

export interface Field {
  id: string;
  page: number;
  rect: Rect;
  type: FieldType;
  name: string;
  label: string;
  value: string | boolean | null;
  checked: boolean;
  background: "white" | "none";
  required: boolean;
  fontSize: number;
  alignment: "left" | "center" | "right";
  maxLength: number | null;
  options: string[];
  group: string | null;
  confidence: number;
  source: string;
  tooltip: string;
}

export interface PageInfo {
  index: number;
  width: number;
  height: number;
  rotation: number;
}

export interface DocumentInfo {
  id: string;
  name: string;
  size: number;
  sha256: string;
  pageCount: number;
  pages: PageInfo[];
  fields: Field[];
  templateMatch: string | null;
}

export interface DetectionResult {
  fields: Field[];
  stats: Record<string, number>;
}

export interface SaveReport {
  outputId: string;
  fileName: string;
  downloadUrl: string;
  sha256: string;
  pageCount: number;
  widgetCount: number;
  flattened: boolean;
  warnings: string[];
  preservedPages: boolean;
}

export interface TemplateSummary {
  id: string;
  name: string;
  description: string;
  pageCount: number;
  fieldCount: number;
  pageSizes: number[][];
}
