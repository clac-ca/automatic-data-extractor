import { ApiError } from "@/api";
import type { FileReadJson } from "@/types/configurations";

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Operation cancelled.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function formatRelative(timestamp?: string): string {
  if (!timestamp) {
    return "";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return date.toLocaleString();
}

export function formatWorkspaceLabel(workspaceId: string): string {
  if (workspaceId.length <= 12) {
    return workspaceId;
  }
  return `${workspaceId.slice(0, 6)}…${workspaceId.slice(-4)}`;
}

export function decodeFileContent(payload: FileReadJson): string {
  if (payload.encoding === "base64") {
    // Preserve UTF-8 characters when decoding base64 payloads from the API.
    const buffer = (
      globalThis as {
        Buffer?: {
          from: (data: string, encoding: string) => { toString: (encoding: string) => string };
        };
      }
    ).Buffer;
    if (buffer) {
      return buffer.from(payload.content, "base64").toString("utf-8");
    }
    if (typeof atob === "function") {
      try {
        const binary = atob(payload.content);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
          bytes[index] = binary.charCodeAt(index);
        }
        if (typeof TextDecoder !== "undefined") {
          return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
        }
        let fallback = "";
        for (let index = 0; index < bytes.length; index += 1) {
          fallback += String.fromCharCode(bytes[index]);
        }
        return fallback;
      } catch {
        // Swallow decode errors and fall through to the raw content.
      }
    }
  }
  return payload.content;
}
