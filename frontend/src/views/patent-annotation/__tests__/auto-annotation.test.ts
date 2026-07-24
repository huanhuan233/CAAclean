import assert from 'node:assert/strict';
import test from 'node:test';
import * as autoAnnotationModule from '../auto-annotation';
import { autoLayoutAnnotations, inferFigureNo, snapPointToInk } from '../auto-annotation';

function imageData(
  width: number,
  height: number,
  pixels: Array<{ x: number; y: number; rgba: [number, number, number, number] }>
) {
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

  assert.equal(inferFigureNo('图 7.pdf', figures, 0), '7');
  assert.equal(inferFigureNo('figure8.pdf', figures, 0), '8');
  assert.equal(inferFigureNo('page.pdf', figures, 1), '8');
  assert.equal(inferFigureNo('page.pdf', figures, 99), '7');
});

test('inferFigureNo recognizes a real Chinese figure filename', () => {
  assert.equal(inferFigureNo('\u56FE4.pdf', [{ figure_no: '4' }], 0), '4');
});

test('inferFigureNo does not silently accept a figure number absent from the specification', () => {
  assert.equal(inferFigureNo('\u56FE99.pdf', [{ figure_no: '1' }, { figure_no: '2' }], 0), '');
});

test('inferFigureNoForSource maps figure PDFs uploaded after document parsing by PDF order', () => {
  const inferFigureNoForSource = (
    autoAnnotationModule as typeof autoAnnotationModule & {
      inferFigureNoForSource?: (
        source: { id: string; kind: 'pdf'; fileName: string },
        sources: Array<{ id: string; kind: 'pdf' | 'step'; fileName: string }>,
        figures: Array<{ figure_no: string }>
      ) => string;
    }
  ).inferFigureNoForSource;
  assert.equal(typeof inferFigureNoForSource, 'function');
  if (!inferFigureNoForSource) return;

  const sources = [
    { id: 'step-1', kind: 'step' as const, fileName: 'model.step' },
    { id: 'pdf-1', kind: 'pdf' as const, fileName: '\u8D44\u6E90527.pdf' },
    { id: 'pdf-2', kind: 'pdf' as const, fileName: '\u8D44\u6E90528.pdf' }
  ];
  const figures = [{ figure_no: '1' }, { figure_no: '2' }, { figure_no: '3' }];

  assert.equal(inferFigureNoForSource(sources[2], sources, figures), '2');
  assert.equal(inferFigureNoForSource({ id: 'pdf-3', kind: 'pdf', fileName: '\u56FE3.pdf' }, sources, figures), '3');
});
