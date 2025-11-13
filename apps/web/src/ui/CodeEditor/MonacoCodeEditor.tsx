import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import Editor, { type BeforeMount, type OnMount } from "@monaco-editor/react";
import clsx from "clsx";

import type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";
import { disposeAdeScriptHelpers, registerAdeScriptHelpers } from "./registerAdeScriptHelpers";

const ADE_DARK_THEME_ID = "ade-dark";
const ADE_DARK_THEME = {
  base: "vs-dark",
  inherit: true,
  rules: [],
  colors: {
    "editor.background": "#1f2430",
    "editor.foreground": "#f3f6ff",
    "editorCursor.foreground": "#fbd38d",
    "editor.lineHighlightBackground": "#2a3142",
    "editorLineNumber.foreground": "#8c92a3",
    "editor.selectionBackground": "#3a4256",
    "editor.inactiveSelectionBackground": "#2d3446",
    "editorGutter.background": "#1c212b",
  },
} as const;

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
  const adeDisposablesRef = useRef<Array<{ dispose: () => void }>>([]);
  const editorPath = useMemo(() => toEditorPath(path), [path]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [editorReady, setEditorReady] = useState(false);
  const adeSuggestTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    saveShortcutRef.current = onSaveShortcut;
  }, [onSaveShortcut]);

  const handleChange = useCallback(
    (nextValue: string | undefined) => {
      onChange(nextValue ?? "");
    },
    [onChange],
  );

  const handleMount = useCallback<OnMount>((editor, monacoInstance) => {
    const modelLanguage = editor.getModel()?.getLanguageId() ?? language;
    adeDisposablesRef.current.forEach((disposable) => disposable.dispose());
    adeDisposablesRef.current = [];
    if (import.meta.env?.DEV) {
      // Surface mount diagnostics so we know which language/path Monaco chose.
      console.debug("[ade] onMount language:", modelLanguage, "editorPath:", editor.getModel()?.uri.toString());
    }
    if (modelLanguage === "python") {
      registerAdeScriptHelpers(monacoInstance, modelLanguage);
      adeLanguageRef.current = modelLanguage;
      const didTypeDisposable = editor.onDidType(() => {
        const model = editor.getModel();
        const position = editor.getPosition();
        if (shouldTriggerAdeSuggest(model, position)) {
          if (adeSuggestTimeoutRef.current !== null) {
            window.clearTimeout(adeSuggestTimeoutRef.current);
          }
          adeSuggestTimeoutRef.current = window.setTimeout(() => {
            if (import.meta.env?.DEV) {
              console.debug("[ade] triggerSuggest (auto)", {
                lineText: model?.getLineContent(position?.lineNumber ?? 0),
                position,
              });
            }
            editor.trigger("ade", "editor.action.triggerSuggest", {});
          }, 0);
        }
      });
      adeDisposablesRef.current.push(didTypeDisposable);
    }
    editor.addCommand(monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS, () => {
      saveShortcutRef.current?.();
    });
    editorRef.current = editor;
    setEditorReady(true);
  }, [language]);

  useEffect(
    () => () => {
      adeDisposablesRef.current.forEach((disposable) => disposable.dispose());
      adeDisposablesRef.current = [];
      if (adeSuggestTimeoutRef.current !== null) {
        window.clearTimeout(adeSuggestTimeoutRef.current);
        adeSuggestTimeoutRef.current = null;
      }
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
        if (!editor) {
          return;
        }
        const target = Math.max(1, Math.floor(lineNumber));
        editor.revealLineInCenter(target);
        editor.setPosition({ lineNumber: target, column: 1 });
        editor.focus();
      },
    }),
    [],
  );

  useEffect(() => {
    if (!editorReady) {
      return;
    }
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
    monacoInstance.editor.defineTheme(ADE_DARK_THEME_ID, ADE_DARK_THEME);
  }, []);

  return (
    <div ref={containerRef} className={clsx("relative h-full w-full", className)}>
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
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Menlo', 'Monaco', monospace",
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
        loading={<div className="flex h-full items-center justify-center text-xs text-slate-400">Loading editor…</div>}
        onMount={handleMount}
      />
    </div>
  );
});

export default MonacoCodeEditor;

function toEditorPath(rawPath: string | undefined): string | undefined {
  if (!rawPath) {
    return undefined;
  }
  if (rawPath.includes("://")) {
    return rawPath;
  }
  const normalized = rawPath.startsWith("/") ? rawPath.slice(1) : rawPath;
  return `inmemory://ade/${normalized}`;
}

type MonacoModel = ReturnType<Parameters<OnMount>[0]["getModel"]>;
type MonacoPosition = ReturnType<Parameters<OnMount>[0]["getPosition"]>;

function shouldTriggerAdeSuggest(model: MonacoModel, position: MonacoPosition | null): boolean {
  if (!model || !position) {
    return false;
  }
  const lineText = model.getLineContent(position.lineNumber);
  const beforeCursor = lineText.slice(0, Math.max(0, position.column - 1));
  const trimmed = beforeCursor.replace(/\s+$/, "");
  return /^(\s*)def(?:\s+([A-Za-z_][\w]*))?$/.test(trimmed);
}
