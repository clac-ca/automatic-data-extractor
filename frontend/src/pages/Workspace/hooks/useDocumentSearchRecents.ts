import { useCallback, useEffect, useMemo, useState } from "react"

type RecentDocument = {
  id: string
  label: string
}

const STORAGE_PREFIX = "ade.search.documents"
const RECENTS_LIMIT = 8

function isRecentDocument(value: unknown): value is RecentDocument {
  if (!value || typeof value !== "object") return false
  const record = value as Record<string, unknown>
  return typeof record.id === "string" && typeof record.label === "string"
}

function readRecents(storageKey: string): RecentDocument[] {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isRecentDocument)
  } catch {
    return []
  }
}

function writeRecents(storageKey: string, recents: RecentDocument[]) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(recents))
  } catch {
    // Ignore storage failures (quota/private mode).
  }
}

export function useDocumentSearchRecents(workspaceId: string) {
  const storageKey = useMemo(
    () => `${STORAGE_PREFIX}.${workspaceId}`,
    [workspaceId]
  )
  const [recents, setRecents] = useState<RecentDocument[]>(() =>
    readRecents(storageKey)
  )

  useEffect(() => {
    setRecents(readRecents(storageKey))
  }, [storageKey])

  useEffect(() => {
    writeRecents(storageKey, recents)
  }, [storageKey, recents])

  const pushRecent = useCallback((item: RecentDocument) => {
    setRecents((prev) => {
      const next = [item, ...prev.filter((entry) => entry.id !== item.id)]
      return next.slice(0, RECENTS_LIMIT)
    })
  }, [])

  const clearRecents = useCallback(() => {
    setRecents([])
  }, [])

  return { recents, pushRecent, clearRecents }
}
