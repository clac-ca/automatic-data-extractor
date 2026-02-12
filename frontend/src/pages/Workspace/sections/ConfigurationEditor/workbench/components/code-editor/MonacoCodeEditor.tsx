import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import CssWorker from "monaco-editor/esm/vs/language/css/css.worker?worker";
import HtmlWorker from "monaco-editor/esm/vs/language/html/html.worker?worker";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import TsWorker from "monaco-editor/esm/vs/language/typescript/ts.worker?worker";
import clsx from "clsx";

import { resolveCssColor } from "@/providers/theme/cssColor";

import type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";
import { disposeAdeScriptHelpers, registerAdeScriptHelpers } from "./registerAdeScriptHelpers";

const ADE_DARK_THEME_ID = "ade-dark";
const ADE_DARK_THEME_FALLBACKS: Record<string, string> = {
  "editor.background": "#1f2430",
  "editor.foreground": "#f3f6ff",
  "editorCursor.foreground": "#fbd38d",
  "editor.lineHighlightBackground": "#2a3142",
  "editorLineNumber.foreground": "#8c92a3",
  "editor.selectionBackground": "#3a4256",
  "editor.inactiveSelectionBackground": "#2d3446",
  "editorGutter.background": "#1c212b",
};

const ADE_DARK_THEME_CSS_VARS: Record<string, string> = {
  "editor.background": "--code-editor-bg",
  "editor.foreground": "--code-editor-fg",
  "editorCursor.foreground": "--code-editor-cursor",
  "editor.lineHighlightBackground": "--code-editor-line-highlight",
  "editorLineNumber.foreground": "--code-editor-line-number",
  "editor.selectionBackground": "--code-editor-selection",
  "editor.inactiveSelectionBackground": "--code-editor-selection-inactive",
  "editorGutter.background": "--code-editor-gutter",
};

const MonacoCodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function MonacoCodeEditor(
  {
    value,
    onChange,
    language = "plaintext",
    path,
    readOnly = false,
    onSaveShortcut,
    className,
    theme = ADE_DARK_THEME_ID,
  }: CodeEditorProps,
  ref,
) {
  const saveShortcutRef = useRef(onSaveShortcut);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const adeLanguageRef = useRef<string | null>(null);
  const editorPath = useMemo(() => toEditorPath(path), [path]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const monacoRef = useRef<Parameters<BeforeMount>[0] | null>(null);
  const [editorReady, setEditorReady] = useState(false);

  useEffect(() => {
    saveShortcutRef.current = onSaveShortcut;
  }, [onSaveShortcut]);

  const handleChange = useCallback(
    (nextValue: string | undefined) => {
      onChange(nextValue ?? "");
    },
    [onChange],
  );

  const handleMount = useCallback<OnMount>(
    (editor, monacoInstance) => {
      const model = editor.getModel();
      const modelLanguage = model?.getLanguageId() ?? language;

      if (import.meta.env?.DEV) {
        console.debug("[ade] MonacoCodeEditor mounted", {
          language: modelLanguage,
          uri: model?.uri.toString(),
        });
      }

      if (modelLanguage === "python") {
        registerAdeScriptHelpers(monacoInstance, modelLanguage);
        adeLanguageRef.current = modelLanguage;
      }

      editor.addCommand(
        monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS,
        () => {
          saveShortcutRef.current?.();
        },
      );

      editorRef.current = editor;
      setEditorReady(true);
    },
    [language],
  );

  useEffect(
    () => () => {
      if (adeLanguageRef.current) {
        disposeAdeScriptHelpers(adeLanguageRef.current);
        adeLanguageRef.current = null;
      }
    },
    [],
  );

  useImperativeHandle(
    ref,
    () => ({
      focus: () => {
        editorRef.current?.focus();
      },
      revealLine: (lineNumber: number) => {
        const editor = editorRef.current;
        if (!editor) return;
        const target = Math.max(1, Math.floor(lineNumber));
        editor.revealLineInCenter(target);
        editor.setPosition({ lineNumber: target, column: 1 });
        editor.focus();
      },
    }),
    [],
  );

  // Manual layout so the editor responds to surrounding layout changes
  useEffect(() => {
    if (!editorReady) return;

    const target = containerRef.current;

    if (target && typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        editorRef.current?.layout();
      });
      observer.observe(target);
      editorRef.current?.layout();
      return () => observer.disconnect();
    }

    const handleResize = () => editorRef.current?.layout();
    window.addEventListener("resize", handleResize);
    handleResize();
    return () => window.removeEventListener("resize", handleResize);
  }, [editorReady]);

  useEffect(() => {
    const handleWorkbenchLayout = () => editorRef.current?.layout();
    window.addEventListener("ade:workbench-layout", handleWorkbenchLayout);
    return () => window.removeEventListener("ade:workbench-layout", handleWorkbenchLayout);
  }, []);

  const handleBeforeMount = useCallback<BeforeMount>((monacoInstance) => {
    ensureMonacoWorkers();
    monacoRef.current = monacoInstance;
    monacoInstance.editor.defineTheme(ADE_DARK_THEME_ID, buildAdeDarkTheme());
  }, []);

  useEffect(() => {
    if (theme !== ADE_DARK_THEME_ID) {
      return;
    }
    const monacoInstance = monacoRef.current;
    if (!monacoInstance) {
      return;
    }
    monacoInstance.editor.defineTheme(ADE_DARK_THEME_ID, buildAdeDarkTheme());
  }, [theme]);

  useEffect(() => {
    if (theme !== ADE_DARK_THEME_ID) {
      return;
    }
    if (typeof MutationObserver === "undefined" || typeof document === "undefined") {
      return;
    }
    const root = document.documentElement;
    if (!root) {
      return;
    }
    const observer = new MutationObserver(() => {
      const monacoInstance = monacoRef.current;
      if (!monacoInstance) {
        return;
      }
      monacoInstance.editor.defineTheme(ADE_DARK_THEME_ID, buildAdeDarkTheme());
    });
    observer.observe(root, { attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => observer.disconnect();
  }, [theme]);

  return (
    <div ref={containerRef} className={clsx("relative h-full w-full min-w-0 overflow-hidden", className)}>
      <Editor
        value={value}
        onChange={handleChange}
        language={language}
        path={editorPath}
        theme={theme}
        beforeMount={handleBeforeMount}
        height="100%"
        width="100%"
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: "var(--app-font-mono)",
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          automaticLayout: true,
          lineNumbersMinChars: 3,
          hover: { enabled: true },
          wordBasedSuggestions: "currentDocument",
          quickSuggestions: { other: true, comments: false, strings: true },
          suggestOnTriggerCharacters: true,
          snippetSuggestions: "inline",
        }}
        loading={
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Loading editor…
          </div>
        }
        onMount={handleMount}
      />
    </div>
  );
});

export default MonacoCodeEditor;

function toEditorPath(rawPath: string | undefined): string | undefined {
  if (!rawPath) return undefined;
  if (rawPath.includes("://")) return rawPath;
  const normalized = rawPath.startsWith("/") ? rawPath.slice(1) : rawPath;
  return `inmemory://ade/${normalized}`;
}

export type MonacoModel = ReturnType<Parameters<OnMount>[0]["getModel"]>;
export type MonacoPosition = ReturnType<Parameters<OnMount>[0]["getPosition"]>;

type MonacoEnvironment = {
  getWorker: (_moduleId: string, label: string) => Worker;
};

function ensureMonacoWorkers(): void {
  const globalScope = globalThis as unknown as { MonacoEnvironment?: MonacoEnvironment };

  if (globalScope.MonacoEnvironment?.getWorker) return;

  globalScope.MonacoEnvironment = {
    getWorker: (_moduleId: string, label: string) => {
      switch (label) {
        case "json":
          return new JsonWorker();
        case "css":
        case "less":
        case "scss":
          return new CssWorker();
        case "html":
        case "handlebars":
        case "razor":
          return new HtmlWorker();
        case "typescript":
        case "javascript":
          return new TsWorker();
        default:
          return new EditorWorker();
      }
    },
  };
}

function buildAdeDarkTheme(): MonacoEditor.IStandaloneThemeData {
  const colors: Record<string, string> = {};
  Object.entries(ADE_DARK_THEME_CSS_VARS).forEach(([token, cssVar]) => {
    colors[token] = resolveCssColor(cssVar, ADE_DARK_THEME_FALLBACKS[token]);
  });
  return {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors,
  };
}
