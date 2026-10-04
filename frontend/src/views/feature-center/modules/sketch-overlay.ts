import * as THREE from 'three';

export type SketchElement = {
  element_id?: string;
  kind?: string;
  construction?: boolean | null;
  display_points_3d_mm?: number[][];
};

export type NativeSketchPayload = { elements?: SketchElement[]; axis?: Record<string, unknown> };

export function createSketchOverlay(scene: THREE.Scene) {
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

  function show(sketch: NativeSketchPayload, color = '#409eff') {
    clear();
    const next = new THREE.Group();
    next.name = '原生草图几何';
    for (const element of sketch.elements || []) {
      const points = (element.display_points_3d_mm || []).filter(point =>
        point.length === 3 && point.every(Number.isFinite)
      );
      if (!points.length) continue;
      const geometry = new THREE.BufferGeometry().setFromPoints(points.map(point => new THREE.Vector3(point[0], point[1], point[2])));
      if (points.length === 1) {
        const marker = new THREE.Points(geometry, new THREE.PointsMaterial({ color, size: 5, sizeAttenuation: false, depthTest: false }));
        marker.name = element.element_id || '草图点';
        next.add(marker);
        continue;
      }
      const material = element.construction
        ? new THREE.LineDashedMaterial({ color, dashSize: 1, gapSize: 0.6, depthTest: false })
        : new THREE.LineBasicMaterial({ color, depthTest: false });
      const line = new THREE.Line(geometry, material);
      line.computeLineDistances();
      line.name = element.element_id || element.kind || '草图元素';
      next.add(line);
    }
    if (!next.children.length) return;
    root = next;
    scene.add(next);
  }

  return { show, clear };
}
