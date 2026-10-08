import * as THREE from 'three';

export interface CompositeContourRegion {
  status: string;
  loops: Array<{ role: string; sampled_points_mm: number[][] }>;
}

export function createCompositeContourOverlay(scene: THREE.Scene) {
  let root: THREE.Group | null = null;

  function clear() {
    if (!root) return;
    scene.remove(root);
    root.traverse(object => {
      if (!(object instanceof THREE.Line)) return;
      object.geometry.dispose();
      (object.material as THREE.Material).dispose();
    });
    root = null;
  }

  function show(region: CompositeContourRegion | null | undefined, color: string): boolean {
    clear();
    if (region?.status !== 'derived_planar' || !Array.isArray(region.loops) ||
        !region.loops.length || region.loops.length > 128) return false;
    const next = new THREE.Group();
    next.name = '单层原生轮廓预览';
    next.userData.selection_overlay = true;
    for (const loop of region.loops) {
      const source = loop.sampled_points_mm;
      if (!Array.isArray(source) || source.length < 3 || source.length > 2048 ||
          source.some(point => !Array.isArray(point) || point.length !== 3 || !point.every(Number.isFinite))) {
        next.children.forEach(object => { (object as THREE.Line).geometry.dispose();
          ((object as THREE.Line).material as THREE.Material).dispose(); });
        return false;
      }
      const points = source.map(point => new THREE.Vector3(point[0], point[1], point[2]));
      points.push(points[0].clone());
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color, depthTest: false, transparent: true, opacity: 0.95 }));
      line.name = loop.role === 'inner' ? '内轮廓预览' : '外轮廓预览';
      next.add(line);
    }
    root = next;
    scene.add(next);
    return true;
  }

  return { clear, show };
}
