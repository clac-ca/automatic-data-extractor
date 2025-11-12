import type { FileBuffer, FileMime } from "../adapters/types";
import { detectLanguageFromPath } from "../adapters/types";

export interface EditorTabState {
  readonly path: string;
  readonly name: string;
  readonly mime: FileMime;
  readonly language: string;
  readonly content: string;
  readonly originalContent: string;
  readonly etag?: string;
  readonly error: string | null;
  readonly isLoading: boolean;
  readonly isSaving: boolean;
  readonly savedAt?: string;
}

export interface EditorState {
  readonly tabs: EditorTabState[];
  readonly activePath: string | null;
}

export type EditorAction =
  | { type: "open/start"; path: string }
  | { type: "open/success"; buffer: FileBuffer }
  | { type: "open/error"; path: string; error: string }
  | { type: "close"; path: string }
  | { type: "activate"; path: string | null }
  | { type: "update"; path: string; content: string }
  | { type: "save/start"; path: string }
  | { type: "save/success"; buffer: FileBuffer; savedAt: string }
  | { type: "save/error"; path: string; error: string }
  | { type: "rename"; fromPath: string; toPath: string }
  | { type: "reset" };

export const initialEditorState: EditorState = {
  tabs: [],
  activePath: null,
};

export function editorReducer(state: EditorState, action: EditorAction): EditorState {
  switch (action.type) {
    case "open/start": {
      const existingIndex = findTabIndex(state.tabs, action.path);
      if (existingIndex >= 0) {
        const existing = state.tabs[existingIndex];
        const updated = { ...existing, isLoading: true, error: null };
        return replaceTab(state, existingIndex, updated, action.path);
      }
      const tab: EditorTabState = {
        path: action.path,
        name: deriveName(action.path),
        mime: inferMime(action.path),
        language: detectLanguageFromPath(action.path),
        content: "",
        originalContent: "",
        etag: undefined,
        error: null,
        isLoading: true,
        isSaving: false,
      };
      return {
        tabs: [...state.tabs, tab],
        activePath: action.path,
      };
    }
    case "open/success": {
      const index = findTabIndex(state.tabs, action.buffer.path);
      const tab: EditorTabState = {
        path: action.buffer.path,
        name: deriveName(action.buffer.path),
        mime: action.buffer.mime,
        language: detectLanguageFromPath(action.buffer.path),
        content: action.buffer.content,
        originalContent: action.buffer.content,
        etag: action.buffer.etag,
        error: null,
        isLoading: false,
        isSaving: false,
        savedAt: new Date().toISOString(),
      };
      if (index >= 0) {
        return replaceTab(state, index, tab, action.buffer.path);
      }
      return {
        tabs: [...state.tabs, tab],
        activePath: action.buffer.path,
      };
    }
    case "open/error": {
      const index = findTabIndex(state.tabs, action.path);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = { ...tab, isLoading: false, error: action.error };
      return replaceTab(state, index, updated, action.path);
    }
    case "close": {
      const index = findTabIndex(state.tabs, action.path);
      if (index === -1) {
        return state;
      }
      const nextTabs = state.tabs.slice();
      nextTabs.splice(index, 1);
      const nextActive =
        state.activePath === action.path
          ? nextTabs.length > 0
            ? nextTabs[Math.min(index, nextTabs.length - 1)].path
            : null
          : state.activePath;
      return { tabs: nextTabs, activePath: nextActive };
    }
    case "activate": {
      return { ...state, activePath: action.path };
    }
    case "update": {
      const index = findTabIndex(state.tabs, action.path);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = { ...tab, content: action.content };
      return replaceTab(state, index, updated, action.path);
    }
    case "save/start": {
      const index = findTabIndex(state.tabs, action.path);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = { ...tab, isSaving: true };
      return replaceTab(state, index, updated, action.path);
    }
    case "save/success": {
      const index = findTabIndex(state.tabs, action.buffer.path);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = {
        ...tab,
        content: action.buffer.content,
        originalContent: action.buffer.content,
        etag: action.buffer.etag,
        isSaving: false,
        error: null,
        savedAt: action.savedAt,
      };
      return replaceTab(state, index, updated, action.buffer.path);
    }
    case "save/error": {
      const index = findTabIndex(state.tabs, action.path);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = { ...tab, isSaving: false, error: action.error };
      return replaceTab(state, index, updated, action.path);
    }
    case "rename": {
      const index = findTabIndex(state.tabs, action.fromPath);
      if (index === -1) {
        return state;
      }
      const tab = state.tabs[index];
      const updated: EditorTabState = {
        ...tab,
        path: action.toPath,
        name: deriveName(action.toPath),
        mime: inferMime(action.toPath),
        language: detectLanguageFromPath(action.toPath),
      };
      const nextTabs = state.tabs.slice();
      nextTabs[index] = updated;
      const activePath = state.activePath === action.fromPath ? action.toPath : state.activePath;
      return { tabs: nextTabs, activePath };
    }
    case "reset": {
      return initialEditorState;
    }
    default:
      return state;
  }
}

export function isTabDirty(tab: EditorTabState): boolean {
  return tab.content !== tab.originalContent;
}

function findTabIndex(tabs: EditorTabState[], path: string) {
  return tabs.findIndex((tab) => tab.path === path);
}

function deriveName(path: string): string {
  const parts = path.split("/");
  const last = parts.pop();
  return last && last.length > 0 ? last : path;
}

function inferMime(path: string): FileMime {
  if (path.endsWith(".py")) {
    return "text/x-python";
  }
  if (path.endsWith(".json")) {
    return "application/json";
  }
  if (path.endsWith(".env")) {
    return "text/x-shellscript";
  }
  return "text/plain";
}

function replaceTab(state: EditorState, index: number, tab: EditorTabState, activePath: string): EditorState {
  const nextTabs = state.tabs.slice();
  nextTabs[index] = tab;
  return { tabs: nextTabs, activePath };
}
