import { clientPointToNormalized } from '../../../utils/normalized-coordinates';
import type { RectLike } from '../../../utils/normalized-coordinates';

export interface CadSceneClick {
  entityId: string;
  worldPoint: [number, number, number];
  screen: {
    x: number;
    y: number;
  };
}

export function normalizeScenePoint(clientX: number, clientY: number, rect: RectLike) {
  return clientPointToNormalized(clientX, clientY, rect);
}
