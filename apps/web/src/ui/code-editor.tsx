import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import Editor, { type OnMount } from "@monaco-editor/react";
import clsx from "clsx";

export interface CodeEditorMarker {
  readonly lineNumber: number;
  readonly message: string;
  readonly severity?: "error" | "warning" | "info";
}

export interface CodeEditorHandle {
  focus: () => void;
  revealLine: (lineNumber: number) => void;
}

interface CodeEditorProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly language?: string;
  readonly readOnly?: boolean;
  readonly onSaveShortcut?: () => void;
  readonly className?: string;
  readonly markers?: readonly CodeEditorMarker[];
}

export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor(
  { value, onChange, language = "plaintext", readOnly = false, onSaveShortcut, className, markers }: CodeEditorProps,
  ref,
) {
  const saveShortcutRef = useRef(onSaveShortcut);
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const monacoRef = useRef<Parameters<OnMount>[1] | null>(null);
  const ownerIdRef = useRef(`ade-code-editor-${Math.random().toString(36).slice(2)}`);
  const markersRef = useRef<readonly CodeEditorMarker[]>(markers ?? []);

  useEffect(() => {
    saveShortcutRef.current = onSaveShortcut;
  }, [onSaveShortcut]);

  useEffect(() => {
    markersRef.current = markers ?? [];
  }, [markers]);

  const handleChange = useCallback(
    (nextValue: string | undefined) => {
      onChange(nextValue ?? "");
    },
    [onChange],
  );

  const applyMarkers = useCallback(() => {
    const editor = editorRef.current;
    const monaco = monacoRef.current;
    if (!editor || !monaco) {
      return;
    }
    const model = editor.getModel();
    if (!model) {
      return;
    }
    const severity = monaco.MarkerSeverity;
    const normalized = markersRef.current.map((marker) => {
      const clampedLine = Math.max(1, Math.min(model.getLineCount(), Math.floor(marker.lineNumber)));
      return {
        startLineNumber: clampedLine,
        endLineNumber: clampedLine,
        startColumn: 1,
        endColumn: model.getLineLength(clampedLine) || 1,
        message: marker.message,
        severity:
          marker.severity === "warning"
            ? severity.Warning
            : marker.severity === "info"
              ? severity.Info
              : severity.Error,
      };
    });
    monaco.editor.setModelMarkers(model, ownerIdRef.current, normalized);
  }, []);

  const handleMount = useCallback<OnMount>((editor, monaco) => {
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
      saveShortcutRef.current?.();
    });
    editorRef.current = editor;
    monacoRef.current = monaco;
    applyMarkers();
  }, [applyMarkers]);

  useEffect(() => {
    applyMarkers();
  }, [applyMarkers, markers]);

  useEffect(() => {
    return () => {
      const editor = editorRef.current;
      const monaco = monacoRef.current;
      if (!editor || !monaco) {
        return;
      }
      const model = editor.getModel();
      if (model) {
        monaco.editor.setModelMarkers(model, ownerIdRef.current, []);
      }
    };
  }, []);

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

  return (
    <div className={clsx("relative h-full w-full", className)}>
      <Editor
        value={value}
        onChange={handleChange}
        language={language}
        theme="vs-dark"
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
        }}
        loading={<div className="flex h-full items-center justify-center text-xs text-slate-400">Loading editor…</div>}
        onMount={handleMount}
      />
    </div>
  );
});
