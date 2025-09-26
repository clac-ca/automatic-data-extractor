export function getCookie(name: string): string | null {
  const target = name + '='
  const candidates = document.cookie.split(';')
  for (const candidate of candidates) {
    const entry = candidate.trim()
    if (entry.startsWith(target)) {
      const value = entry.slice(target.length)
      return value ? decodeURIComponent(value) : null
    }
  }
  return null
}
