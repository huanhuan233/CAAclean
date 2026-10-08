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
      if (object instanceof THREE.Line || object instanceof THREE.Mesh) {
        object.geometry.dispose();
        (object.material as THREE.Material).dispose();
      }
    });
    root = null;
  }

  function show(region: CompositeContourRegion | null | undefined, color: string,
    nominalDirection?: { status: string; vector: number[] | null }): boolean {
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
    const vector = nominalDirection?.vector;
    if (nominalDirection?.status === 'derived_planar_nominal' && vector?.length === 3 &&
        vector.every(Number.isFinite) && next.children.length) {
      const first = region.loops[0].sampled_points_mm;
      const extent = Math.max(1, new THREE.Vector3(first[0][0], first[0][1], first[0][2])
        .distanceTo(new THREE.Vector3(first[1][0], first[1][1], first[1][2])) / 5);
      const direction = new THREE.Vector3(vector[0], vector[1], vector[2]);
      if (direction.lengthSq() > 1e-12) {
        const arrow = new THREE.ArrowHelper(direction.normalize(),
          new THREE.Vector3(first[0][0], first[0][1], first[0][2]), extent, color);
        arrow.name = '派生名义方向（非真实铺覆纤维轨迹）';
        next.add(arrow);
      }
    }
    root = next;
    scene.add(next);
    return true;
  }

  function regionMesh(region: { display_vertices_mm: number[][]; display_triangles: number[][] },
    color: string, opacity: number): THREE.Mesh | null {
    const vertices = region.display_vertices_mm;
    const triangles = region.display_triangles;
    if (!Array.isArray(vertices) || !Array.isArray(triangles) || vertices.length < 3 ||
        vertices.length > 20000 || triangles.length < 1 || triangles.length > 10000 ||
        vertices.some(point => !Array.isArray(point) || point.length !== 3 || !point.every(Number.isFinite)) ||
        triangles.some(face => !Array.isArray(face) || face.length !== 3 ||
          face.some(index => !Number.isInteger(index) || index < 0 || index >= vertices.length))) return null;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices.flat(), 3));
    geometry.setIndex(triangles.flat());
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color, side: THREE.DoubleSide, transparent: true, opacity, depthTest: false, depthWrite: false
    }));
    return mesh;
  }

  function showRegion(region: { display_vertices_mm: number[][]; display_triangles: number[][] }, color: string): boolean {
    clear();
    const mesh = regionMesh(region, color, 0.42);
    if (!mesh) return false;
    const next = new THREE.Group();
    next.name = '名义厚度区域预览';
    next.userData.selection_overlay = true;
    next.add(mesh);
    root = next;
    scene.add(next);
    return true;
  }

  function showCoverage(regions: Array<{ region_id: string; display_vertices_mm: number[][];
    display_triangles: number[][] }>, color: string, selectedRegionId = ''): boolean {
    clear();
    if (!Array.isArray(regions) || !regions.length || regions.length > 512) return false;
    const next = new THREE.Group();
    next.name = '名义厚度区域预览';
    next.userData.selection_overlay = true;
    for (const region of regions) {
      const mesh = regionMesh(region, color, region.region_id === selectedRegionId ? 0.42 : 0.12);
      if (!mesh) {
        next.children.forEach(object => { (object as THREE.Mesh).geometry.dispose();
          ((object as THREE.Mesh).material as THREE.Material).dispose(); });
        return false;
      }
      mesh.userData.composite_region_id = region.region_id;
      next.add(mesh);
    }
    root = next;
    scene.add(next);
    return true;
  }

  function pickRegion(raycaster: THREE.Raycaster): string | null {
    if (root?.name !== '名义厚度区域预览') return null;
    const hit = raycaster.intersectObjects(root.children, false)[0];
    return typeof hit?.object.userData.composite_region_id === 'string'
      ? hit.object.userData.composite_region_id : null;
  }

  return { clear, show, showRegion, showCoverage, pickRegion };
}
