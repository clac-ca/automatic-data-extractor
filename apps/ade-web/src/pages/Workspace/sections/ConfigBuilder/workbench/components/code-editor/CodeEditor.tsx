import { forwardRef, lazy, Suspense } from "react";
import clsx from "clsx";

import type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";

const LazyMonacoCodeEditor = lazy(() => import("./MonacoCodeEditor"));

export const CodeEditor = forwardRef<CodeEditorHandle, CodeEditorProps>(function CodeEditor(
  props,
  ref,
) {
  const { className, ...rest } = props;

  return (
    <Suspense
      fallback={
        <div className={clsx("relative h-full w-full", className)}>
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            Loading editor…
          </div>
        </div>
      }
    >
      <LazyMonacoCodeEditor {...rest} ref={ref} className={className} />
    </Suspense>
  );
});

export type { CodeEditorHandle, CodeEditorProps } from "./CodeEditor.types";
