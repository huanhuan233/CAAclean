/**
 * =============================================================================
 * UI Demo Mock Data for Component Library Page
 * =============================================================================
 *
 * WARNING: This file contains purely frontend demo / placeholder data.
 * It exists ONLY to fill visual gaps in the UI where the backend does not
 * currently provide certain fields.
 *
 * The following guidelines apply:
 *  - Real API data always takes precedence over mock data.
 *  - All mock data is clearly marked with "UI_DEMO" in its property names
 *    or in comments.
 *  - This file does NOT create, submit, or modify backend state.
 *  - When a real backend API becomes available, delete the relevant mock
 *    maps and replace them with the real data source.
 *
 * Coverage:
 *  1. componentUsageMap   – stable call-volume per build_id (UI display only)
 *  2. paramFieldMap       – extra parameter fields (DN, PN, STEP/drawing status)
 *  3. catalogTreeData     – static catalog tree for left navigation display
 * =============================================================================
 */

/**
 * callVolume (调用量): UI demo field.
 * Returns a stable pseudo-random number based on build_id string hash.
 * This ensures the same build_id always gets the same call count within
 * a session, and across refreshes within the same page load.
 *
 * Formula: simple string hash → mod 300 + 10 → result in [10, 309].
 */
function stableHash(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash // Convert to 32bit integer
  }
  return Math.abs(hash)
}

/** Map build_id → call volume. Built lazily; stable within a session. */
const callVolumeCache = new Map<string, number>()

/**
 * Get a stable demo call volume for a given build_id.
 * @param buildId - The build identifier
 * @returns call count between 10 and 309
 *
 * [UI_DEMO] This is a purely frontend display field. No backend API exists
 * for call volume tracking. Remove this when the real API becomes available.
 */
export function getDemoCallVolume(buildId: string): number {
  if (!callVolumeCache.has(buildId)) {
    callVolumeCache.set(buildId, (stableHash(buildId) % 300) + 10)
  }
  return callVolumeCache.get(buildId)!
}

/** Catalog path display helper — maps category_code to label. */
const catalogCategoryLabels: Record<string, string> = {
  '01': '01 连接紧固件',
  '02': '02 轴系与支承',
  '03': '03 传动件',
  '04': '04 弹性元件',
  '05': '05 密封元件',
  '06': '06 支撑与结构',
  '07': '07 动力与执行'
}

/**
 * Get catalog display label from category code.
 * Falls back to the code itself if not found.
 */
export function getCatalogLabel(code: string): string {
  return catalogCategoryLabels[code] || code
}

/**
 * =============================================================================
 * YAML Local Upload Storage
 * =============================================================================
 *
 * Stores locally-uploaded YAML content in localStorage per build_id.
 * This is a UI ONLY feature — the YAML is never sent to any backend.
 *
 * [UI_MOCK] localStorage key pattern: component-library-local-yaml:{buildId}
 * =============================================================================
 */

const LOCAL_YAML_PREFIX = 'component-library-local-yaml:'

export interface LocalYamlRecord {
  filename: string
  size: number
  modifiedAt: string
  content: string
  uploadedAt: string
}

/**
 * Save a locally-uploaded YAML to localStorage.
 * [UI_MOCK] Does not affect server-side data.
 */
export function saveLocalYaml(buildId: string, record: LocalYamlRecord): void {
  try {
    localStorage.setItem(LOCAL_YAML_PREFIX + buildId, JSON.stringify(record))
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

/**
 * Retrieve a locally-uploaded YAML from localStorage.
 * Returns null if none was saved.
 * [UI_MOCK] Returns frontend-only cached data.
 */
export function getLocalYaml(buildId: string): LocalYamlRecord | null {
  try {
    const raw = localStorage.getItem(LOCAL_YAML_PREFIX + buildId)
    if (!raw) return null
    return JSON.parse(raw) as LocalYamlRecord
  } catch {
    return null
  }
}

/**
 * Remove a locally-uploaded YAML from localStorage.
 */
export function clearLocalYaml(buildId: string): void {
  localStorage.removeItem(LOCAL_YAML_PREFIX + buildId)
}
