/** Display-only SVG approximation uses exact circular arc commands for DXF bulge. */
export function polylinePath(vertices: number[][], closed: boolean): string {
  if (!vertices.length) return '';
  const commands = [`M ${vertices[0][0]} ${-vertices[0][1]}`];
  const count = closed ? vertices.length : vertices.length - 1;
  for (let index = 0; index < count; index += 1) {
    const start = vertices[index];
    const end = vertices[(index + 1) % vertices.length];
    const bulge = start[4] || 0;
    const chord = Math.hypot(end[0] - start[0], end[1] - start[1]);
    if (Math.abs(bulge) < 1e-12 || chord === 0) {
      commands.push(`L ${end[0]} ${-end[1]}`);
    } else {
      const radius = chord * (1 + bulge * bulge) / (4 * Math.abs(bulge));
      commands.push(`A ${radius} ${radius} 0 ${Math.abs(bulge) > 1 ? 1 : 0} ${bulge > 0 ? 1 : 0} ${end[0]} ${-end[1]}`);
    }
  }
  return commands.join(' ');
}
