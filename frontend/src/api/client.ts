export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

const DEFAULT_HEADERS = {
  "Content-Type": "application/json",
};

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api";

export type ApiClient = {
  get<T>(path: string, init?: RequestInit): Promise<T>;
};

export function createApiClient(token: string): ApiClient {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...DEFAULT_HEADERS,
        ...(init.headers ?? {}),
        Authorization: `Bearer ${token}`,
      },
    });

    const contentType = response.headers.get("content-type");
    const isJson = contentType?.includes("application/json");
    const payload = isJson ? await response.json() : await response.text();

    if (!response.ok) {
      const detail = typeof payload?.detail === "string" ? payload.detail : response.statusText;
      throw new ApiError(response.status, detail ?? "Unknown API error");
    }

    return payload as T;
  }

  return {
    get: request,
  };
}
