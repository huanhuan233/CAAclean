"""Bent pipe answers come from construction parameters, never the analyzer."""
import math
import os
from pathlib import Path

import pytest

from app.cad.parser_runner import run_freecad_job
from app.core.config import Settings


@pytest.mark.asyncio
async def test_bent_tubes_measure_sections_and_reject_non_tubes(tmp_path):
    if os.environ.get('P7_LIVE_FREECAD') != '1':
        pytest.skip('set P7_LIVE_FREECAD=1')
    settings = Settings()
    fixture = await run_freecad_job(Path(__file__).parent / 'fixtures/bent_tubes.py',
                                   {'directory': str(tmp_path)}, tmp_path / 'fixture-job', settings)
    assert all(row['valid'] and row['solids'] == 1 for row in fixture['fixtures'].values())
    names = list(fixture['fixtures'])
    result = await run_freecad_job(Path(settings.cad_script_dir) / 'tube_geometry.py',
        {'solids': [{'solid_id': name, 'asset_path': str(tmp_path / (name + '.brep'))} for name in names]},
        tmp_path / 'analysis-job', settings)
    assert result['status'] == 'success', result
    rows = {row['solid_id']: row for row in result['records']}
    for name in ('elbow', 'combo', 'split', 'transformed'):
        row = rows[name]
        assert row['status'] == 'confirmed_bent_hollow_tube', (name, row)
        assert row['section']['outer_diameter_mm'] == pytest.approx(8)
        assert row['section']['inner_diameter_mm'] == pytest.approx(6)
        assert row['section']['wall_thickness_mm'] == pytest.approx(1)
        assert row['path']['length_mm'] == pytest.approx(15 * math.pi + (0 if name == 'elbow' else 60))
        assert row['section']['uniformity_status'] == 'verified_analytic_constant_section'
        assert len(row['section']['samples']) == 3 * len(row['path']['segments'])
        assert all(s['status'] == 'verified' for s in row['section']['samples'])
        assert row['verification']['volume_relative_residual'] < 1e-6
        assert len(row['ends']) == 2
        assert all(segment['outer_face_indices'] and segment['inner_face_indices'] for segment in row['path']['segments'])
    for name in ('rod', 'closed', 'damaged', 'eccentric', 'neighbor'):
        assert not rows[name]['status'].startswith('confirmed'), (name, rows[name])
        assert 'section' not in rows[name]
    assert result['diagnostics']['loaded_shapes'] == len(names)
    clearance = await run_freecad_job(Path(settings.cad_script_dir) / 'tube_geometry.py',
        {'solids': [{'solid_id': name, 'asset_path': str(tmp_path / (name + '.brep'))} for name in ('elbow', 'neighbor')],
         'target_tube_solid_id': 'elbow'}, tmp_path / 'clearance-job', settings)
    assert clearance['status'] == 'success', clearance
    gap = clearance['clearances'][0]
    assert gap['status'] == 'evaluated'
    assert gap['distance_mm'] == pytest.approx(2, abs=1e-5)
    assert gap['witnesses'][0]['s_mm'] == pytest.approx(7.5 * math.pi, abs=1e-5)
