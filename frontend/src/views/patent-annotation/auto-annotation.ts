import { clamp01, normalizePoint } from './geometry';
import type { Point2D } from './types';

export interface SnapOptions {
  radius?: number;
  threshold?: number;
}

export interface AutoLayoutAnchor {
  refNo: string;
  anchor: Point2D;
}

export interface AutoLayoutItem extends AutoLayoutAnchor {
  elbow: Point2D;
  label: Point2D;
}

export interface PatentFigureLike {
  figure_no: string;
}

export function snapPointToInk(point: Point2D, imageData: ImageData, options: SnapOptions = {}): Point2D {
  const radius = Math.max(0, Math.trunc(options.radius ?? 12));
  const threshold = options.threshold ?? 180;
  const width = Math.max(1, imageData.width);
  const height = Math.max(1, imageData.height);
  const originX = Math.round(clamp01(point.x) * (width - 1));
  const originY = Math.round(clamp01(point.y) * (height - 1));
  let best: { x: number; y: number; distance: number } | null = null;

  for (let y = Math.max(0, originY - radius); y <= Math.min(height - 1, originY + radius); y += 1) {
    for (let x = Math.max(0, originX - radius); x <= Math.min(width - 1, originX + radius); x += 1) {
      const distance = (x - originX) ** 2 + (y - originY) ** 2;
      if (distance > radius ** 2) continue;
      const offset = (y * width + x) * 4;
      const alpha = imageData.data[offset + 3] ?? 0;
      const darkness = ((imageData.data[offset] ?? 255) + (imageData.data[offset + 1] ?? 255) + (imageData.data[offset + 2] ?? 255)) / 3;
      if (alpha <= 0 || darkness >= threshold) continue;
      if (!best || distance < best.distance) best = { x, y, distance };
    }
  }

  if (!best) return normalizePoint(point);
  return {
    x: width === 1 ? 0 : best.x / (width - 1),
    y: height === 1 ? 0 : best.y / (height - 1)
  };
}

export function autoLayoutAnnotations(anchors: AutoLayoutAnchor[], options: { minSpacing?: number } = {}): AutoLayoutItem[] {
  const minSpacing = options.minSpacing ?? 0.055;
  const left = anchors.filter(item => item.anchor.x > 0.5);
  const right = anchors.filter(item => item.anchor.x <= 0.5);
  return [...layoutGroup(left, 'left', minSpacing), ...layoutGroup(right, 'right', minSpacing)].sort(
    (a, b) => anchors.findIndex(item => item.refNo === a.refNo) - anchors.findIndex(item => item.refNo === b.refNo)
  );
}

export function inferFigureNo(fileName: string, figures: PatentFigureLike[], sourceIndex: number): string {
  const chinese = /图\s*(\d+)/i.exec(fileName);
  if (chinese) return chinese[1];
  const english = /figure\s*(\d+)/i.exec(fileName);
  if (english) return english[1];
  return figures[sourceIndex]?.figure_no ?? figures[0]?.figure_no ?? '';
}

function layoutGroup(items: AutoLayoutAnchor[], side: 'left' | 'right', minSpacing: number): AutoLayoutItem[] {
  const sorted = [...items].sort((a, b) => a.anchor.y - b.anchor.y || a.refNo.localeCompare(b.refNo, undefined, { numeric: true }));
  const ys = distribute(sorted.map(item => clamp01(item.anchor.y)), minSpacing);
  return sorted.map((item, index) => {
    const anchor = normalizePoint(item.anchor);
    const label = { x: side === 'left' ? 0.06 : 0.94, y: ys[index] };
    const elbow = {
      x: side === 'left' ? Math.min(anchor.x - 0.04, 0.18) : Math.max(anchor.x + 0.04, 0.82),
      y: label.y
    };
    return { ...item, anchor, elbow: normalizePoint(elbow), label };
  });
}

function distribute(values: number[], minSpacing: number) {
  const lower = 0.06;
  const upper = 0.94;
  const spacing = minSpacing + 0.000001;
  const result = values.map(value => Math.min(upper, Math.max(lower, value)));
  for (let index = 1; index < result.length; index += 1) {
    result[index] = Math.max(result[index], result[index - 1] + spacing);
  }
  const overflow = result.length ? result[result.length - 1] - upper : 0;
  if (overflow > 0) {
    for (let index = 0; index < result.length; index += 1) result[index] -= overflow;
  }
  const underflow = result.length ? lower - result[0] : 0;
  if (underflow > 0) {
    for (let index = 0; index < result.length; index += 1) result[index] += underflow;
  }
  return result;
}
