import type { PageViewport } from "pdfjs-dist";
import type { Rect } from "./types";

/**
 * Field rectangles live in one canonical space: the unrotated crop box,
 * origin at its top-left, y down, PDF points. PDF.js works in user space
 * (y up, origin at the crop box bottom-left) and applies rotation when it
 * builds a viewport. Everything that crosses that boundary goes through
 * these two functions so no component does its own arithmetic.
 */
export type ViewBox = [number, number, number, number];

export function canonicalToUser(x: number, y: number, viewBox: ViewBox): [number, number] {
  return [viewBox[0] + x, viewBox[3] - y];
}

export function userToCanonical(x: number, y: number, viewBox: ViewBox): [number, number] {
  return [x - viewBox[0], viewBox[3] - y];
}

export function canonicalToCssRect(rect: Rect, viewport: PageViewport, viewBox: ViewBox): {
  left: number;
  top: number;
  width: number;
  height: number;
} {
  const [ax, ay] = canonicalToUser(rect[0], rect[1], viewBox);
  const [bx, by] = canonicalToUser(rect[2], rect[3], viewBox);
  const [x1, y1] = viewport.convertToViewportPoint(ax, ay);
  const [x2, y2] = viewport.convertToViewportPoint(bx, by);
  return {
    left: Math.min(x1, x2),
    top: Math.min(y1, y2),
    width: Math.abs(x2 - x1),
    height: Math.abs(y2 - y1),
  };
}

export function cssPointToCanonical(
  cssX: number,
  cssY: number,
  viewport: PageViewport,
  viewBox: ViewBox,
): [number, number] {
  const [ux, uy] = viewport.convertToPdfPoint(cssX, cssY);
  return userToCanonical(ux, uy, viewBox);
}

/** CSS pixels per PDF point for this viewport. */
export function pointScale(viewport: PageViewport): number {
  return viewport.scale;
}

export function fitFontSize(heightPt: number): number {
  return Math.round(Math.max(5, Math.min(10, heightPt * 0.62)) * 10) / 10;
}
