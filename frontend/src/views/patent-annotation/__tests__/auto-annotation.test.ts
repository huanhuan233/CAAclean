import assert from 'node:assert/strict';
import test from 'node:test';
import { autoLayoutAnnotations, inferFigureNo, snapPointToInk } from '../auto-annotation';

function imageData(width: number, height: number, pixels: Array<{ x: number; y: number; rgba: [number, number, number, number] }>) {
  const data = new Uint8ClampedArray(width * height * 4);
  data.fill(255);
  for (let index = 3; index < data.length; index += 4) data[index] = 255;
  for (const pixel of pixels) {
    const offset = (pixel.y * width + pixel.x) * 4;
    data[offset] = pixel.rgba[0];
    data[offset + 1] = pixel.rgba[1];
    data[offset + 2] = pixel.rgba[2];
    data[offset + 3] = pixel.rgba[3];
  }
  return { width, height, data } as ImageData;
}

test('snapPointToInk snaps to the nearest dark opaque pixel', () => {
  const data = imageData(10, 10, [{ x: 7, y: 6, rgba: [0, 0, 0, 255] }]);

  assert.deepEqual(snapPointToInk({ x: 0.68, y: 0.6 }, data, { radius: 3 }), { x: 7 / 9, y: 6 / 9 });
});

test('snapPointToInk respects radius, transparency, and boundaries', () => {
  const data = imageData(10, 10, [
    { x: 9, y: 9, rgba: [0, 0, 0, 255] },
    { x: 0, y: 0, rgba: [0, 0, 0, 0] }
  ]);

  assert.deepEqual(snapPointToInk({ x: 0, y: 0 }, data, { radius: 1 }), { x: 0, y: 0 });
  assert.deepEqual(snapPointToInk({ x: 1.4, y: 1.4 }, data, { radius: 2 }), { x: 1, y: 1 });
});

test('autoLayoutAnnotations keeps crowded labels inside bounds with spacing', () => {
  const anchors = Array.from({ length: 6 }, (_, index) => ({
    refNo: String(index + 1),
    anchor: { x: 0.8, y: 0.1 + index * 0.01 }
  }));

  const labels = autoLayoutAnnotations(anchors).map(item => item.label);

  assert.ok(labels.every(label => label.x === 0.06 && label.y >= 0.06 && label.y <= 0.94));
  for (let index = 1; index < labels.length; index += 1) {
    assert.ok(labels[index].y - labels[index - 1].y >= 0.055);
  }
});

test('inferFigureNo maps Chinese, English, and source-index fallback', () => {
  const figures = [{ figure_no: '7' }, { figure_no: '8' }];

  assert.equal(inferFigureNo('图 4.pdf', figures, 0), '4');
  assert.equal(inferFigureNo('figure2.pdf', figures, 0), '2');
  assert.equal(inferFigureNo('page.pdf', figures, 1), '8');
  assert.equal(inferFigureNo('page.pdf', figures, 99), '7');
});
