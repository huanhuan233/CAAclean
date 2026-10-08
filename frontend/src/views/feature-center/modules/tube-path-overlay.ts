import * as THREE from 'three';

export interface TubeSegmentView {
  kind?: string;
  start_mm?: number[];
  end_mm?: number[];
  center_mm?: number[];
  plane_normal?: number[];
  bend_deg?: number;
  radius_mm?: number;
  source_id?: string;
}

function vector(value: number[] | undefined): THREE.Vector3 | null {
  return value?.length === 3 && value.every(Number.isFinite)
    ? new THREE.Vector3(value[0], value[1], value[2]) : null;
}

export function sampleTubeSegment(segment: TubeSegmentView, chordErrorMm = 0.1): THREE.Vector3[] {
  const start = vector(segment.start_mm);
  const end = vector(segment.end_mm);
  if (!start || !end) return [];
  if (segment.kind === 'line') return [start, end];
  if (segment.kind !== 'arc') return [];
  const center = vector(segment.center_mm);
  const normal = vector(segment.plane_normal);
  const angle = Number(segment.bend_deg) * Math.PI / 180;
  const radius = Number(segment.radius_mm);
  if (!center || !normal || normal.lengthSq() < 1e-20 || !Number.isFinite(angle) ||
      !Number.isFinite(radius) || radius <= 0 || angle <= 0 || angle >= 2 * Math.PI ||
      Math.abs(start.distanceTo(center) - radius) > 1e-3) return [];
  normal.normalize();
  const safeError = Math.min(Math.max(chordErrorMm, 0.001), radius / 2);
  const maxStep = 2 * Math.acos(Math.max(-1, Math.min(1, 1 - safeError / radius)));
  const count = Math.max(16, Math.ceil(angle / maxStep));
  if (count > 1024) return [];
  const radial = start.clone().sub(center);
  const points = Array.from({ length: count + 1 }, (_, index) =>
    radial.clone().applyAxisAngle(normal, angle * index / count).add(center));
  if (points[points.length - 1].distanceTo(end) > Math.max(0.01, chordErrorMm)) return [];
  return points;
}

export function createTubePathOverlay(scene: THREE.Scene) {
  let root: THREE.Group | null = null;
  function clear() {
    if (!root) return;
    scene.remove(root);
    root.traverse(object => {
      const line = object as THREE.Line;
      line.geometry?.dispose();
      if (Array.isArray(line.material)) line.material.forEach(material => material.dispose());
      else line.material?.dispose();
    });
    root = null;
  }
  function show(segments: TubeSegmentView[], color: string) {
    clear();
    const next = new THREE.Group();
    next.name = '导管中心线';
    next.userData.selection_overlay = true;
    for (const segment of segments) {
      const points = sampleTubeSegment(segment);
      if (points.length < 2) continue;
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color, depthTest: false }));
      line.name = segment.source_id || '中心线段';
      next.add(line);
    }
    if (!next.children.length) return false;
    root = next;
    scene.add(next);
    return true;
  }
  return { clear, show };
}
