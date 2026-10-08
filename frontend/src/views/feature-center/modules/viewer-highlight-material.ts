import * as THREE from 'three';

interface MaterialSnapshot {
  color?: number;
  emissive?: number;
  emissiveIntensity?: number;
  transparent: boolean;
  opacity: number;
  depthWrite: boolean;
  depthTest: boolean;
  side: THREE.Side;
}

/** Three.js Color does not parse the space-separated CSS rgb() form used by Element Plus. */
export function normalizeCssColorForThree(color: string): string {
  const match = /^rgb\(\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*[,\s]\s*(\d{1,3})\s*\)$/i.exec(color.trim());
  if (!match) return color;
  return `#${match.slice(1).map(value => Math.min(255, Number(value)).toString(16).padStart(2, '0')).join('')}`;
}

/** Each GLB material is cloned before registration, so a selection only changes its own mesh. */
export function rememberMaterial(material: THREE.Material) {
  const standard = material as THREE.MeshStandardMaterial;
  const snapshot: MaterialSnapshot = {
    color: standard.color?.getHex(), emissive: standard.emissive?.getHex(),
    emissiveIntensity: standard.emissiveIntensity,
    transparent: material.transparent, opacity: material.opacity,
    depthWrite: material.depthWrite, depthTest: material.depthTest, side: material.side
  };
  material.userData.cad_original_material = snapshot;
}

export function restoreMaterial(material: THREE.Material) {
  const snapshot = material.userData.cad_original_material as MaterialSnapshot | undefined;
  if (!snapshot) return;
  const standard = material as THREE.MeshStandardMaterial;
  if (snapshot.color != null && standard.color) standard.color.setHex(snapshot.color);
  if (snapshot.emissive != null && standard.emissive) standard.emissive.setHex(snapshot.emissive);
  if (snapshot.emissiveIntensity != null) standard.emissiveIntensity = snapshot.emissiveIntensity;
  material.transparent = snapshot.transparent;
  material.opacity = snapshot.opacity;
  material.depthWrite = snapshot.depthWrite;
  material.depthTest = snapshot.depthTest;
  material.side = snapshot.side;
}

export function applySelectedMaterial(material: THREE.Material, color: string, uncertain: boolean) {
  const standard = material as THREE.MeshStandardMaterial;
  standard.color?.set(color);
  standard.emissive?.set(color);
  if (standard.emissive) standard.emissiveIntensity = 0.35;
  if (uncertain) {
    // A candidate inner wall can be hidden behind an outer tube wall. Draw only
    // its mapped finite mesh as an explicit preview; never tint adjacent support faces.
    material.side = THREE.DoubleSide;
    material.depthTest = false;
    material.depthWrite = false;
    material.transparent = true;
    material.opacity = 0.82;
  }
}
