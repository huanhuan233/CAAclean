export type RectLike = Pick<DOMRect, 'left' | 'top' | 'width' | 'height'>;

export function clamp01(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function clientPointToNormalized(clientX: number, clientY: number, rect: RectLike) {
  if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };

  return {
    x: clamp01((clientX - rect.left) / rect.width),
    y: clamp01((clientY - rect.top) / rect.height)
  };
}
