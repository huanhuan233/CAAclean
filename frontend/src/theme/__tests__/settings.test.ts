import assert from 'node:assert/strict';
import test from 'node:test';
import { overrideThemeSettings, themeSettings } from '../settings';

test('approved theme and page settings are the application defaults', () => {
  assert.equal(themeSettings.themeColor, '#0632F6');
  assert.equal(themeSettings.recommendColor, false);
  assert.equal(themeSettings.isInfoFollowPrimary, true);
  assert.deepEqual(themeSettings.otherColor, {
    info: '#2080f0',
    success: '#52c41a',
    warning: '#faad14',
    error: '#f5222d'
  });
  assert.equal(themeSettings.layout.mode, 'vertical');
  assert.equal(themeSettings.layout.scrollMode, 'content');
  assert.deepEqual(themeSettings.page, { animate: true, animateMode: 'fade-slide' });
  assert.equal(themeSettings.header.height, 45);
  assert.deepEqual(themeSettings.header.breadcrumb, { visible: true, showIcon: true });
  assert.deepEqual(themeSettings.tab, { visible: true, cache: true, height: 44, mode: 'chrome' });
});

test('production migration overrides the approved fields only', () => {
  assert.equal(overrideThemeSettings.themeColor, '#0632F6');
  assert.equal(overrideThemeSettings.header?.height, 45);
  assert.equal(overrideThemeSettings.layout?.scrollMode, 'content');
  assert.equal(overrideThemeSettings.tab?.mode, 'chrome');
  assert.equal(overrideThemeSettings.footer, undefined);
  assert.equal(overrideThemeSettings.watermark, undefined);
});
