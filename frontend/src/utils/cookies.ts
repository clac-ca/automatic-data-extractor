export function getCookie(name: string): string | null {
  const prefix = name + '='
  const entry = document.cookie.split('; ').find((cookie) => cookie.startsWith(prefix))
  if (!entry) {
    return null
  }
  const value = entry.slice(prefix.length)
  return value ? decodeURIComponent(value) : null
}
