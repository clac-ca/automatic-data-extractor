const DEFAULT_BASE_URL = "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export type ApiOptions = RequestInit & {
  readonly parseJson?: boolean;
  readonly returnRawResponse?: boolean;
};

export interface ProblemDetails {
  readonly type?: string;
  readonly title?: string;
  readonly status?: number;
  readonly detail?: string;
  readonly errors?: Record<string, string[]>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem?: ProblemDetails;

  constructor(message: string, status: number, problem?: ProblemDetails) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = DEFAULT_BASE_URL) {
    this.baseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  }

  async request<T = unknown>(path: string, options: ApiOptions = {}): Promise<T> {
    const {
      parseJson = true,
      returnRawResponse = false,
      headers: headersInit,
      body,
      method: rawMethod,
      credentials,
      ...rest
    } = options;

    const method = (rawMethod ?? "GET").toUpperCase();
    const url = this.composeUrl(path);

    const requestHeaders = new Headers({
      Accept: parseJson && !returnRawResponse ? "application/json" : "*/*",
    });

    this.copyHeaders(requestHeaders, headersInit);

    if (body && !(body instanceof FormData) && !requestHeaders.has("Content-Type")) {
      requestHeaders.set("Content-Type", "application/json");
    }

    if (!SAFE_METHODS.has(method) && !requestHeaders.has("X-CSRF-Token")) {
      const csrfToken = readCookie(getCsrfCookieName());
      if (csrfToken) {
        requestHeaders.set("X-CSRF-Token", csrfToken);
      }
    }

    const response = await fetch(url, {
      ...rest,
      method,
      headers: requestHeaders,
      body,
      credentials: credentials ?? "include",
    });

    if (!response.ok) {
      const problem = await this.tryParseProblem(response);
      const message = problem?.title ?? `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, problem);
    }

    if (returnRawResponse) {
      return response as unknown as T;
    }

    if (!parseJson) {
      return undefined as T;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    return text ? (JSON.parse(text) as T) : (undefined as T);
  }

  private composeUrl(path: string) {
    if (!path.startsWith("/")) {
      throw new Error("API paths must include a leading slash.");
    }

    if (!this.baseUrl) {
      return path;
    }

    return `${this.baseUrl}${path}`;
  }

  private copyHeaders(target: Headers, init?: HeadersInit) {
    if (!init) {
      return;
    }

    if (init instanceof Headers) {
      init.forEach((value, key) => target.set(key, value));
      return;
    }

    if (Array.isArray(init)) {
      init.forEach(([key, value]) => target.set(key, value));
      return;
    }

    Object.entries(init).forEach(([key, value]) => {
      if (typeof value === "undefined") {
        return;
      }
      target.set(key, Array.isArray(value) ? value.join(", ") : value);
    });
  }

  private async tryParseProblem(response: Response): Promise<ProblemDetails | undefined> {
    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return undefined;
    }

    try {
      return (await response.json()) as ProblemDetails;
    } catch (error) {
      console.warn("Failed to parse problem details", error);
      return undefined;
    }
  }
}

function getCsrfCookieName() {
  const fromEnv = import.meta.env.VITE_SESSION_CSRF_COOKIE ?? import.meta.env.VITE_SESSION_CSRF_COOKIE_NAME;
  if (typeof fromEnv === "string" && fromEnv.trim().length > 0) {
    return fromEnv.trim();
  }
  return "backend_app_csrf";
}

function readCookie(name: string) {
  if (typeof document === "undefined") {
    return null;
  }

  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [rawName, ...valueParts] = cookie.trim().split("=");
    if (rawName === name) {
      return decodeURIComponent(valueParts.join("="));
    }
  }

  return null;
}

const defaultClient = new ApiClient(import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL);

export function get<T>(path: string, options?: ApiOptions) {
  return defaultClient.request<T>(path, { ...options, method: "GET" });
}

export function post<T>(path: string, body?: unknown, options?: ApiOptions) {
  const payload =
    body instanceof FormData ? body : body === undefined ? undefined : JSON.stringify(body);
  return defaultClient.request<T>(path, {
    ...options,
    method: "POST",
    body: payload,
  });
}

export function del<T>(path: string, options?: ApiOptions) {
  return defaultClient.request<T>(path, { ...options, method: "DELETE" });
}

export function patch<T>(path: string, body?: unknown, options?: ApiOptions) {
  const payload = body === undefined ? undefined : JSON.stringify(body);
  return defaultClient.request<T>(path, {
    ...options,
    method: "PATCH",
    body: payload,
  });
}

export function put<T>(path: string, body?: unknown, options?: ApiOptions) {
  const payload = body === undefined ? undefined : JSON.stringify(body);
  return defaultClient.request<T>(path, {
    ...options,
    method: "PUT",
    body: payload,
  });
}
