import * as THREE from 'three';
import type { GeometryQueryResponse } from '@/service/api/cad';

type Point = number[];

export function createMeasurementOverlay(scene: THREE.Scene) {
  let root: THREE.Group | null = null;

  function clear() {
    if (!root) return;
    scene.remove(root);
    root.traverse(object => {
      const mesh = object as THREE.Mesh;
      mesh.geometry?.dispose();
      const material = mesh.material;
      if (Array.isArray(material)) material.forEach(item => item.dispose());
      else material?.dispose();
    });
    root = null;
  }

  function point(group: THREE.Group, coordinates: Point, color: THREE.Color) {
    if (coordinates.length !== 3) return;
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1.5, 10, 8),
      new THREE.MeshBasicMaterial({ color, depthTest: false }));
    mesh.position.set(coordinates[0], coordinates[1], coordinates[2]);
    mesh.userData.pickable = false;
    group.add(mesh);
  }

  function line(group: THREE.Group, points: Point[], color: THREE.Color) {
    if (points.length < 2) return;
    const geometry = new THREE.BufferGeometry().setFromPoints(points.map(item =>
      new THREE.Vector3(item[0], item[1], item[2])));
    const object = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color, depthTest: false }));
    object.userData.pickable = false;
    group.add(object);
  }

  function show(result: GeometryQueryResponse | null, colorValue: string) {
    clear();
    if (!result || !['success', 'multiple'].includes(result.status) || !result.values) return;
    const color = new THREE.Color(colorValue);
    const group = new THREE.Group();
    group.name = 'measurement-overlay';
    group.userData.pickable = false;
    const values = result.values;
    if (result.operation === 'distance') {
      const pairs = values.nearest_points as Array<{ a: Point; b: Point }> | undefined;
      if (pairs?.[0]) {
        point(group, pairs[0].a, color);
        point(group, pairs[0].b, color);
        line(group, [pairs[0].a, pairs[0].b], color);
      }
    } else if (result.operation === 'local_thickness') {
      const start = values.start as Point | undefined;
      const end = values.end as Point | undefined;
      if (start && end) {
        point(group, start, color);
        point(group, end, color);
        line(group, [start, end], color);
      }
    } else if (result.operation === 'section') {
      const curves = values.curves as Array<{ display_points?: Point[] }> | undefined;
      curves?.forEach(curve => line(group, curve.display_points || [], color));
    }
    if (group.children.length) {
      root = group;
      scene.add(group);
    }
  }

  return { show, clear };
}
