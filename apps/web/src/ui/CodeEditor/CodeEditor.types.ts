export interface CodeEditorHandle {
  focus: () => void;
  revealLine: (lineNumber: number) => void;
}

export interface CodeEditorProps {
  readonly value: string;
  readonly onChange: (value: string) => void;
  readonly language?: string;
  readonly readOnly?: boolean;
  readonly onSaveShortcut?: () => void;
  readonly className?: string;
}
