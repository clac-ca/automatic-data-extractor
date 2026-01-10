import type * as Monaco from "monaco-editor";

import type { AdeFunctionSpec } from "./adeScriptApi";
import { getHoverSpec, getSnippetSpecs } from "./adeScriptApi";

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
  if (!registration) return;
  registration.refCount -= 1;
  if (registration.refCount <= 0) {
    registration.disposables.forEach((disposable) => disposable.dispose());
    registrations.delete(lang);
  }
}

/* ---------- Hover ---------- */

function registerHoverProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerHoverProvider(languageId, {
    provideHover(model, position) {
      const word = model.getWordAtPosition(position);
      if (!word) return null;

      const spec = getHoverSpec(word.word);
      if (!spec) return null;

      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      );

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

/* ---------- Completion: minimal, file-scoped, always on in ADE files ---------- */

function registerCompletionProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  const EMPTY_COMPLETIONS = { suggestions: [] as Monaco.languages.CompletionItem[] };

  return monaco.languages.registerCompletionItemProvider(languageId, {
    // Helpful but not critical; Ctrl+Space always works
    triggerCharacters: [" ", "d", "t", "_"],

    provideCompletionItems(model, position) {
      const specs = getSnippetSpecs();
      if (!specs || specs.length === 0) {
        return EMPTY_COMPLETIONS;
      }

      const lineNumber = position.lineNumber;
      const prefix = model.getValueInRange(
        new monaco.Range(lineNumber, 1, lineNumber, position.column),
      );
      const trimmed = prefix.replace(/\s+$/, "");
      const trailing = prefix.length - trimmed.length; // whitespace after the last token
      const identMatch = /[A-Za-z_][\w]*$/.exec(trimmed);
      const replaceStartCol = identMatch
        ? position.column - trailing - identMatch[0].length
        : position.column - trailing;
      const range = new monaco.Range(
        lineNumber,
        Math.max(1, replaceStartCol),
        lineNumber,
        position.column,
      );

      const suggestions = specs.map((spec, index) =>
        createSnippetSuggestion(monaco, spec, range, index),
      );

      if (import.meta.env?.DEV) {
        console.debug("[ade-completions] ADE specs for file", {
          specs: specs.map((s) => s.name),
        });
        console.debug(
          "[ade-completions] ADE suggestions",
          suggestions.map((s) => s.label),
        );
      }

      return { suggestions };
    },
  });
}

/* ---------- Signature help ---------- */

function registerSignatureProvider(
  monaco: typeof import("monaco-editor"),
  languageId: string,
): Monaco.IDisposable {
  return monaco.languages.registerSignatureHelpProvider(languageId, {
    signatureHelpTriggerCharacters: ["(", ","],
    signatureHelpRetriggerCharacters: [","],
    provideSignatureHelp(model, position) {
      const lineContent = model.getLineContent(position.lineNumber);
      const prefix = lineContent.slice(0, position.column);
      const match = /([A-Za-z_][\w]*)\s*\($/.exec(prefix);
      if (!match) {
        return null;
      }

      const spec = getHoverSpec(match[1]);
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
          activeParameter: Math.min(
            Math.max(activeParameter, 0),
            Math.max(parameters.length - 1, 0),
          ),
        },
        dispose: () => {
          // nothing to clean up for one-off signature hints
        },
      };
    },
  });
}

function computeActiveParameter(prefix: string): number {
  const parenIndex = prefix.lastIndexOf("(");
  if (parenIndex === -1) return 0;
  const argsSoFar = prefix.slice(parenIndex + 1);
  if (!argsSoFar.trim()) return 0;
  return argsSoFar.split(",").length - 1;
}

/* ---------- Snippet suggestion creation ---------- */

function createSnippetSuggestion(
  monaco: typeof import("monaco-editor"),
  spec: AdeFunctionSpec,
  range: Monaco.Range,
  index: number,
): Monaco.languages.CompletionItem {
  return {
    label: spec.label,
    kind: monaco.languages.CompletionItemKind.Snippet,
    insertText: spec.snippet,
    insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
    documentation: { value: spec.doc },
    detail: spec.signature,
    range,
    sortText: `0${index}`,
  };
}
