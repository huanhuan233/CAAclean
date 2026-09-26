# Frontend Theme Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the currently approved blue theme and page-layout settings the application defaults and migrate existing production browser settings once per build.

**Architecture:** Keep `themeSettings` as the single complete default object used by development mode and reset behavior. Add a deeply partial `overrideThemeSettings` migration object so production initialization replaces only the approved fields while preserving unrelated saved preferences.

**Tech Stack:** Vue 3, TypeScript, Pinia theme store, Node test runner through `tsx`, `vue-tsc`

## Global Constraints

- Primary color is exactly `#0632F6`.
- Recommended color processing remains disabled and information color follows primary.
- Existing success, warning, and error colors remain `#52C41A`, `#FAAD14`, and `#F5222D`.
- Layout remains vertical with content scrolling, enabled `fade-slide` transitions, a 45px header, visible breadcrumb icons, and a cached 44px Chrome-style tab bar.
- Do not disable the theme drawer or remove the user's ability to adjust settings after initialization.
- Do not overwrite unrelated production preferences during migration.

---

### Task 1: Lock the approved defaults and migration fields

**Files:**
- Create: `frontend/src/theme/__tests__/settings.test.ts`
- Modify: `frontend/src/theme/settings.ts`

**Interfaces:**
- Consumes: `themeSettings` and `overrideThemeSettings` from `frontend/src/theme/settings.ts`.
- Produces: a complete `themeSettings: App.Theme.ThemeSetting` and deeply partial `overrideThemeSettings` consumed by `initThemeSettings()`.

- [ ] **Step 1: Write the failing configuration test**

```ts
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
```

- [ ] **Step 2: Run the test and confirm it fails on the old primary color and header height**

Run:

```powershell
& $NodePath node_modules\tsx\dist\cli.mjs --test src/theme/__tests__/settings.test.ts
```

Expected: FAIL because `themeSettings.themeColor` is `#646cff` and `themeSettings.header.height` is `56`.

- [ ] **Step 3: Implement the defaults and deeply partial migration object**

In `frontend/src/theme/settings.ts`, set `themeColor` to `#0632F6` and `header.height` to `45`. Define a recursive partial type and use it for an override object containing only the approved top-level and nested keys:

```ts
type DeepPartial<T> = {
  [Key in keyof T]?: T[Key] extends object ? DeepPartial<T[Key]> : T[Key];
};

export const overrideThemeSettings: DeepPartial<App.Theme.ThemeSetting> = {
  themeScheme: 'light',
  recommendColor: false,
  themeColor: '#0632F6',
  otherColor: {
    info: '#2080f0',
    success: '#52c41a',
    warning: '#faad14',
    error: '#f5222d'
  },
  isInfoFollowPrimary: true,
  layout: { mode: 'vertical', scrollMode: 'content' },
  page: { animate: true, animateMode: 'fade-slide' },
  header: { height: 45, breadcrumb: { visible: true, showIcon: true } },
  tab: { visible: true, cache: true, height: 44, mode: 'chrome' }
};
```

- [ ] **Step 4: Run the focused test and type checker**

Run:

```powershell
& $NodePath node_modules\tsx\dist\cli.mjs --test src/theme/__tests__/settings.test.ts
& $NodePath node_modules\vue-tsc\bin\vue-tsc.js --noEmit
```

Expected: both commands exit 0.

- [ ] **Step 5: Verify formatting and the running development page**

Run `git diff --check -- frontend/src/theme/settings.ts frontend/src/theme/__tests__/settings.test.ts`. Refresh `http://127.0.0.1:9999/component-build` and verify the primary CSS color is `#0632F6`, header height is 45px, and the theme drawer reports the approved settings.
