import '@testing-library/jest-dom/vitest'

const mutableEnv = import.meta.env as unknown as Record<string, string | undefined>
if (!mutableEnv.VITE_API_BASE_URL) {
  mutableEnv.VITE_API_BASE_URL = 'http://127.0.0.1:8000'
}
