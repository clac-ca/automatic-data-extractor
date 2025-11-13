import type * as Monaco from "monaco-editor";

import type { AdeFunctionSpec } from "./adeScriptApi";
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
    triggerCharacters: [" ", "t", "_"],
    provideCompletionItems(model, position) {
      const filePath = getModelPath(model);
      if (!isAdeConfigFile(filePath)) {
        return EMPTY_COMPLETIONS;
      }
      const specs = getSnippetSpecs(filePath);
      logCompletionDebug("ADE specs for file", {
        filePath,
        specs: specs.map((spec) => spec.name),
      });
      if (specs.length === 0) {
        return EMPTY_COMPLETIONS;
      }
      const context = getCompletionContext(monaco, model, position);
      logCompletionDebug("ADE completion context", context);
      if (!context) {
        return EMPTY_COMPLETIONS;
      }
      const filteredSpecs = specs.filter((spec) => matchesTrigger(spec, context));
      const suggestions = filteredSpecs.map((spec, index) => createSnippetSuggestion(monaco, spec, context, index));
      logCompletionDebug("ADE suggestions", suggestions.map((s) => s.label));
      return {
        suggestions,
      };
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
  const rawPath = uri.path || uri.toString();
  if (!rawPath) {
    return undefined;
  }
  return rawPath.startsWith("/") ? rawPath.slice(1) : rawPath;
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

type SnippetContext = {
  range: Monaco.Range;
  typedName: string;
  typedNameLower: string;
};

const EMPTY_COMPLETIONS = { suggestions: [] as Monaco.languages.CompletionItem[] };

function getCompletionContext(
  monaco: typeof import("monaco-editor"),
  model: Monaco.editor.ITextModel,
  position: Monaco.Position,
): SnippetContext | null {
  const lineText = model.getLineContent(position.lineNumber);
  const beforeCursor = lineText.slice(0, Math.max(0, position.column - 1));
  const trimmedBeforeCursor = beforeCursor.replace(/\s+$/, "");
  const match = /^(\s*)def(?:\s+([A-Za-z_][\w]*))?/.exec(trimmedBeforeCursor);
  if (!match) {
    return null;
  }
  const indent = match[1] || "";
  const typedName = (match[2] || "").trim();
  const startColumn = indent.length + 1;
  const range = new monaco.Range(position.lineNumber, startColumn, position.lineNumber, position.column);
  return {
    range,
    typedName,
    typedNameLower: typedName.toLowerCase(),
  };
}

function matchesTrigger(spec: AdeFunctionSpec, context: SnippetContext): boolean {
  if (!context.typedName) {
    return true;
  }
  const triggers = getSnippetTriggers(spec);
  return triggers.some((trigger) => {
    return trigger.startsWith(context.typedNameLower) || context.typedNameLower.startsWith(trigger);
  });
}

function getSnippetTriggers(spec: AdeFunctionSpec): string[] {
  if (spec.name === "detect_*") {
    return ["detect"];
  }
  return [spec.name.toLowerCase()];
}

function createSnippetSuggestion(
  monaco: typeof import("monaco-editor"),
  spec: AdeFunctionSpec,
  context: SnippetContext,
  index: number,
): Monaco.languages.CompletionItem {
  return {
    label: spec.label,
    kind: monaco.languages.CompletionItemKind.Snippet,
    insertText: spec.snippet,
    insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
    documentation: { value: spec.doc },
    detail: spec.signature,
    range: context.range,
    sortText: `0${index}`,
  };
}

const SHOULD_LOG_COMPLETIONS =
  typeof import.meta !== "undefined" && !!import.meta.env && Boolean(import.meta.env.DEV);

function logCompletionDebug(label: string, payload: unknown): void {
  if (!SHOULD_LOG_COMPLETIONS) {
    return;
  }
  // eslint-disable-next-line no-console -- intentional dev-only diagnostics
  console.debug(`[ade-completions] ${label}`, payload);
}
