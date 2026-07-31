export type ComponentSpecRequestResult<T> = {
  data?: T | null
  error?: unknown
}

export type LoadedComponentSpec<T> = {
  document: T
  offline: boolean
}

export function isOfflineRequestError(error: unknown): boolean {
  if (!error || typeof error !== 'object') return false
  const candidate = error as { code?: string; response?: unknown }
  if (candidate.code === 'ERR_CANCELED') return false
  return candidate.response == null
}

export async function loadComponentSpecWithFallback<T>(
  buildId: string,
  fetchDocument: (buildId: string) => Promise<ComponentSpecRequestResult<T>>,
  localDocument: (buildId: string) => T
): Promise<LoadedComponentSpec<T>> {
  try {
    const result = await fetchDocument(buildId)
    if (!result.error && result.data) {
      return { document: result.data, offline: false }
    }
  } catch {
    // The local template is the intentional offline fallback.
  }

  return {
    document: localDocument(buildId),
    offline: true
  }
}
