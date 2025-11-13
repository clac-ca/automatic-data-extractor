import type * as Monaco from "monaco-editor";

import { getHoverSpec, getSnippetSpecs, isAdeConfigFile } from "./adeScriptApi";

type Registration = {
  disposables: Monaco.IDisposable[];
  refCount: number;
};

const registrations = new Map<string, Registration>();

export function registerAdeScriptHelpers(
  monaco: typeof import("monaco-editor"),
  languageId = "python",
): void {
  const lang = languageId || "python";
  const existing = registrations.get(lang);
  if (existing) {
    existing.refCount += 1;
    return;
  }

  const disposables: Monaco.IDisposable[] = [
    registerHoverProvider(monaco, lang),
    registerCompletionProvider(monaco, lang),
    registerSignatureProvider(monaco, lang),
  ];

  registrations.set(lang, { disposables, refCount: 1 });
}

export function disposeAdeScriptHelpers(languageId = "python"): void {
  const lang = languageId || "python";
  const registration = registrations.get(lang);
  if (!registration) {
    return;
  }
  registration.refCount -= 1;
  if (registration.refCount <= 0) {
    registration.disposables.forEach((disposable) => disposable.dispose());
    registrations.delete(lang);
  }
}

function registerHoverProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerHoverProvider(languageId, {
    provideHover(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return null;
      }
      const word = model.getWordAtPosition(position);
      if (!word) {
        return null;
      }
      const spec = getHoverSpec(word.word, filePath);
      if (!spec) {
        return null;
      }
      const range = new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn);
      return {
        range,
        contents: [
          { value: ["```python", spec.signature, "```"].join("\n") },
          { value: spec.doc },
        ],
      };
    },
  });
}

function registerCompletionProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerCompletionItemProvider(languageId, {
    triggerCharacters: [" "],
    provideCompletionItems(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return { suggestions: [] };
      }
      const context = getSnippetContext(monaco, model, position);
      if (!context) {
        return { suggestions: [] };
      }
      const specs = getSnippetSpecs(filePath);
      if (specs.length === 0) {
        return { suggestions: [] };
      }

      const suggestions = specs.map((spec, index) => ({
        label: spec.label,
        kind: monaco.languages.CompletionItemKind.Snippet,
        insertText: spec.snippet,
        insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
        documentation: { value: spec.doc },
        detail: spec.signature,
        range: context.range,
        sortText: `0${index}`,
      }));

      return { suggestions };
    },
  });
}

function registerSignatureProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerSignatureHelpProvider(languageId, {
    signatureHelpTriggerCharacters: ["(", ","],
    signatureHelpRetriggerCharacters: [","],
    provideSignatureHelp(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return null;
      }
      const lineContent = model.getLineContent(position.lineNumber);
      const prefix = lineContent.slice(0, position.column);
      const match = /([A-Za-z_][\w]*)\s*\($/.exec(prefix);
      if (!match) {
        return null;
      }
      const spec = getHoverSpec(match[1], filePath);
      if (!spec) {
        return null;
      }
      const activeParameter = computeActiveParameter(prefix);
      const parameters = spec.parameters.map((param) => ({ label: param }));
      return {
        value: {
          signatures: [
            {
              label: spec.signature,
              documentation: spec.doc,
              parameters,
            },
          ],
          activeSignature: 0,
          activeParameter: Math.min(Math.max(activeParameter, 0), Math.max(parameters.length - 1, 0)),
        },
        dispose: () => {
          // nothing to clean up for one-off signature hints
        },
      };
    },
  });
}

function getModelPath(model: Monaco.editor.ITextModel | undefined): string | undefined {
  if (!model) {
    return undefined;
  }
  const uri = model.uri;
  if (!uri) {
    return undefined;
  }
  return uri.path || uri.toString();
}

function computeActiveParameter(prefix: string): number {
  const parenIndex = prefix.lastIndexOf("(");
  if (parenIndex === -1) {
    return 0;
  }
  const argsSoFar = prefix.slice(parenIndex + 1);
  if (!argsSoFar.trim()) {
    return 0;
  }
  return argsSoFar.split(",").length - 1;
}

function getSnippetContext(
  monaco: typeof import("monaco-editor"),
  model: Monaco.editor.ITextModel,
  position: Monaco.Position,
): { range: Monaco.Range } | null {
  const lineText = model.getLineContent(position.lineNumber);
  const beforeCursor = lineText.slice(0, Math.max(0, position.column - 1));
  const withoutIndent = beforeCursor.replace(/^\s+/, "");
  const trimmed = withoutIndent.replace(/\s+$/, "");
  if (!trimmed.startsWith("def")) {
    return null;
  }
  const indentLength = beforeCursor.length - withoutIndent.length;
  const startColumn = indentLength + 1;
  const range = new monaco.Range(position.lineNumber, startColumn, position.lineNumber, position.column);
  return { range };
}
