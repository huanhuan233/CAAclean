import assert from 'node:assert/strict';
import test from 'node:test';
import { tubeGeometryTitle, tubeObjectStatus, tubeSectionRows, tubeSectionSamples } from '../modules/tube-section-view';

test('弯管外径与中心线弯曲半径分开，候选不升级', () => {
  assert.equal(tubeGeometryTitle('confirmed_bent_hollow_tube'), '弯管（空心）');
  assert.equal(tubeObjectStatus('confirmed_bent_hollow_tube'), '已核验空心弯管');
  assert.equal(tubeGeometryTitle('candidate'), '几何候选');
  const rows = tubeSectionRows({ outer_diameter_mm: 6, inner_diameter_mm: 5, wall_thickness_mm: 0.5,
    uniformity_status: 'verified_analytic_constant_section', method: 'paired_cylindrical_toroidal_walls_and_normal_sections',
    samples: [{ status: 'verified', segment_order: 1 }, { status: 'verified', segment_order: 2 }] });
  assert.deepEqual(rows.find(row => row[0] === '截面外径'), ['截面外径', '6.000 mm']);
  assert.deepEqual(rows.find(row => row[0] === '几何壁厚'), ['几何壁厚', '0.500 mm']);
  assert.equal(rows.some(row => String(row[0]).includes('弯曲半径')), false);
});

test('局部样本不宣称等厚，缺失尺寸不填零；选中弯段只看该段的核验截面', () => {
  assert.equal(tubeSectionRows({}).some(row => row[1] === '0.000 mm'), false);
  assert.equal(tubeSectionRows({ wall_thickness_mm: 1 }).some(row => row[0] === '截面一致性'), false);
  const section = { samples: [{ segment_order: 1, station_s_mm: 10 }, { segment_order: 2, station_s_mm: 20 }] };
  assert.deepEqual(tubeSectionSamples(section, 2), [{ segment_order: 2, station_s_mm: 20 }]);
});
