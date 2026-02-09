export type FileNameParts = {
  baseName: string;
  extension: string;
};

export function splitFileName(name: string): FileNameParts {
  const lastDotIndex = name.lastIndexOf(".");
  if (lastDotIndex <= 0) {
    return {
      baseName: name,
      extension: "",
    };
  }
  return {
    baseName: name.slice(0, lastDotIndex),
    extension: name.slice(lastDotIndex),
  };
}

export function composeFileName(parts: FileNameParts): string {
  return parts.extension ? `${parts.baseName}${parts.extension}` : parts.baseName;
}
