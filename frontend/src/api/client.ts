export interface ApiClientOptions {
  readonly baseUrl?: string;
  readonly fetchImplementation?: typeof fetch;
}

export interface RequestOptions extends RequestInit {
  readonly query?: Record<string, string | number | boolean | null | undefined>;
  readonly json?: unknown;
  readonly parseJson?: boolean;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? getDefaultBaseUrl();
    this.fetchImpl = options.fetchImplementation ?? fetch.bind(globalThis);
  }

  async get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, options);
  }

  async post<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, options);
  }

  async patch<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("PATCH", path, options);
  }

  async delete<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("DELETE", path, options);
  }

  private async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = this.buildUrl(path, options.query);
    const headers = new Headers(options.headers ?? {});

    if (!headers.has("Content-Type") && options.json !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    this.applyCsrfHeader(headers, method);

    const response = await this.fetchImpl(url, {
      ...options,
      method,
      credentials: options.credentials ?? "include",
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body
    });

    if (!response.ok) {
      throw await this.parseError(response);
    }

    if (response.status === 204 || options.parseJson === false) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }

  private buildUrl(
    path: string,
    query?: Record<string, string | number | boolean | null | undefined>
  ): string {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const isAbsoluteBase = /^https?:/i.test(this.baseUrl);

    let url = isAbsoluteBase
      ? new URL(normalizedPath, this.baseUrl).toString()
      : `${trimTrailingSlash(this.baseUrl)}${normalizedPath}`;

    if (query && Object.keys(query).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(query)) {
        if (value === undefined || value === null) {
          continue;
        }
        searchParams.set(key, String(value));
      }
      const separator = url.includes("?") ? "&" : "?";
      const queryString = searchParams.toString();
      if (queryString) {
        url = `${url}${separator}${queryString}`;
      }
    }

    return url;
  }

  private async parseError(response: Response): Promise<ApiError> {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch (error) {
      detail = await response.text();
    }

    const message =
      typeof detail === "object" && detail && "message" in (detail as Record<string, unknown>)
        ? String((detail as Record<string, unknown>).message)
        : response.statusText || "Request failed";

    return new ApiError(message, response.status, detail);
  }

  private applyCsrfHeader(headers: Headers, method: string): void {
    const upperMethod = method.toUpperCase();
    const safeMethods = new Set(["GET", "HEAD", "OPTIONS"]);
    if (safeMethods.has(upperMethod)) {
      return;
    }

    if (headers.has("X-CSRF-Token")) {
      return;
    }

    if (typeof document === "undefined") {
      return;
    }

    const token = readCookie("ade_csrf");
    if (token) {
      headers.set("X-CSRF-Token", token);
    }
  }
}

function getDefaultBaseUrl(): string {
  const envBase = typeof import.meta !== "undefined" ? import.meta.env?.VITE_API_BASE_URL : undefined;
  if (envBase) {
    return envBase;
  }

  if (typeof import.meta !== "undefined" && import.meta.env?.DEV) {
    return "http://127.0.0.1:8000";
  }

  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }

  return "http://127.0.0.1:8000";
}

function trimTrailingSlash(value: string): string {
  if (!value) {
    return "";
  }
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export const apiClient = new ApiClient();

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookieString = document.cookie ?? "";
  if (!cookieString) {
    return null;
  }

  const prefix = `${name}=`;
  const parts = cookieString.split(/;\s*/);
  for (const part of parts) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return null;
}
