import type { ProblemDetails } from "./types";

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

export interface ApiClientOptions extends RequestInit {
  parseJson?: boolean;
}

const DEFAULT_API_BASE_URL = "/api";

function normalizeBaseUrl(baseUrl: string) {
  if (!baseUrl) {
    return "";
  }

  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

function resolveUrl(baseUrl: string, path: string) {
  if (!path.startsWith("/")) {
    throw new Error("API paths must start with a leading slash");
  }

  if (!baseUrl) {
    return path;
  }

  return `${baseUrl}${path}`;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = DEFAULT_API_BASE_URL) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
  }

  async request<T = unknown>(path: string, init: ApiClientOptions = {}): Promise<T> {
    const { parseJson = true, headers, ...rest } = init;

    const url = resolveUrl(this.baseUrl, path);

    const response = await fetch(url, {
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...headers,
      },
      ...rest,
    });

    if (!response.ok) {
      const problem = await this.parseProblem(response);
      const message = problem?.title || `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, problem);
    }

    if (!parseJson) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }

    return JSON.parse(text) as T;
  }

  private async parseProblem(response: Response): Promise<ProblemDetails | undefined> {
    const contentType = response.headers.get("content-type");
    if (contentType?.includes("application/json")) {
      try {
        return (await response.json()) as ProblemDetails;
      } catch (error) {
        console.warn("Failed to parse problem details", error);
      }
    }

    return undefined;
  }
}

function resolveBaseUrlFromEnv() {
  const fromEnv = import.meta.env.VITE_API_BASE_URL;
  if (typeof fromEnv === "string" && fromEnv.trim() !== "") {
    return fromEnv.trim();
  }

  return DEFAULT_API_BASE_URL;
}

export const apiClient = new ApiClient(resolveBaseUrlFromEnv());

export async function get<T>(path: string, init?: ApiClientOptions) {
  return apiClient.request<T>(path, { method: "GET", ...init });
}

export async function post<T>(path: string, body?: unknown, init?: ApiClientOptions) {
  return apiClient.request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    ...init,
  });
}

export async function del<T>(path: string, init?: ApiClientOptions) {
  return apiClient.request<T>(path, { method: "DELETE", ...init });
}
