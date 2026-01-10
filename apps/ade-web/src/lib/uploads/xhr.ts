import { buildApiHeaders, resolveApiUrl } from "@api/client";
import { ApiError, isProblemDetailsContentType, type ProblemDetails } from "@api/errors";

export type UploadProgress = {
  readonly loaded: number;
  readonly total: number | null;
  readonly percent: number | null;
};

export type UploadResult<T> = {
  readonly data: T | null;
  readonly status: number;
};

export interface UploadHandle<T> {
  readonly promise: Promise<UploadResult<T>>;
  readonly abort: () => void;
}

interface UploadRequestOptions {
  readonly method?: string;
  readonly headers?: HeadersInit;
  readonly onProgress?: (progress: UploadProgress) => void;
  readonly signal?: AbortSignal;
}

const abortError =
  typeof DOMException !== "undefined"
    ? new DOMException("Aborted", "AbortError")
    : Object.assign(new Error("Aborted"), { name: "AbortError" });

export function uploadWithProgressXHR<T>(
  path: string,
  body: FormData,
  options: UploadRequestOptions = {},
): UploadHandle<T> {
  const { method = "POST", headers, onProgress, signal } = options;
  const url = resolveApiUrl(path);
  const xhr = new XMLHttpRequest();

  const promise = new Promise<UploadResult<T>>((resolve, reject) => {
    xhr.open(method, url);
    xhr.withCredentials = true;

    const requestHeaders = buildApiHeaders(method, headers);
    requestHeaders.forEach((value, key) => {
      xhr.setRequestHeader(key, value);
    });

    xhr.upload.onprogress = (event) => {
      const total = event.lengthComputable ? event.total : null;
      const percent = total && total > 0 ? Math.round((event.loaded / total) * 100) : null;
      onProgress?.({ loaded: event.loaded, total, percent });
    };

    xhr.onload = () => {
      const status = xhr.status;
      const contentType = xhr.getResponseHeader("Content-Type") ?? "";
      const responseText = xhr.responseText ?? "";
      const data = parseJsonResponse<T>(responseText, contentType);

      if (status >= 200 && status < 300) {
        resolve({ data, status });
        return;
      }

      const problem = parseProblem(responseText, contentType);
      const message =
        problem?.title ??
        problem?.detail ??
        `Request failed with status ${status}`;
      reject(new ApiError(message, status, problem));
    };

    xhr.onerror = () => {
      reject(new ApiError("Upload failed due to a network error.", xhr.status || 0));
    };

    xhr.onabort = () => {
      reject(abortError);
    };

    xhr.send(body);
  });

  const handleAbort = () => {
    xhr.abort();
  };

  if (signal) {
    if (signal.aborted) {
      xhr.abort();
    } else {
      signal.addEventListener("abort", handleAbort);
      void promise.finally(() => signal.removeEventListener("abort", handleAbort));
    }
  }

  return {
    promise,
    abort: () => xhr.abort(),
  };
}

function parseJsonResponse<T>(payload: string, contentType: string): T | null {
  if (!payload) {
    return null;
  }
  if (!contentType.includes("application/json")) {
    return null;
  }
  try {
    return JSON.parse(payload) as T;
  } catch {
    return null;
  }
}

function parseProblem(payload: string, contentType: string): ProblemDetails | undefined {
  if (!payload || !isProblemDetailsContentType(contentType)) {
    return undefined;
  }
  try {
    return JSON.parse(payload) as ProblemDetails;
  } catch {
    return undefined;
  }
}
