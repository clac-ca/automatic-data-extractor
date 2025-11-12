import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import Fuse from "fuse.js";

interface PaletteItem {
  readonly path: string;
  readonly name: string;
}

interface CommandPaletteProps {
  readonly isOpen: boolean;
  readonly files: readonly PaletteItem[];
  readonly onSelect: (path: string) => void;
  readonly onClose: () => void;
}

export function CommandPalette({ isOpen, files, onSelect, onClose }: CommandPaletteProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const fuse = useMemo(() => new Fuse(files, { keys: ["name", "path"], threshold: 0.3 }), [files]);
  const results = useMemo(() => {
    if (query.trim().length === 0) {
      return files;
    }
    return fuse.search(query).map((entry) => entry.item);
  }, [files, fuse, query]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setQuery("");
    setActiveIndex(0);
    const id = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [isOpen]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const handleSelect = (path: string) => {
    onSelect(path);
    onClose();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => Math.min(results.length - 1, prev + 1));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => Math.max(0, prev - 1));
    }
    if (event.key === "Enter" && results[activeIndex]) {
      event.preventDefault();
      handleSelect(results[activeIndex].path);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/60 p-6"
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-xl rounded-2xl border border-slate-700/60 bg-slate-900 shadow-2xl">
        <div className="border-b border-slate-700/60 p-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="w-full rounded-xl border border-slate-700/60 bg-slate-950/40 px-3 py-2 text-sm text-white placeholder:text-slate-400 focus:border-brand-500 focus:outline-none"
            placeholder="Search files"
            aria-label="Search files"
          />
        </div>
        <ul className="max-h-72 overflow-y-auto py-2">
          {results.length === 0 ? (
            <li className="px-4 py-6 text-center text-sm text-slate-400">No files match “{query}”.</li>
          ) : (
            results.map((item, index) => (
              <li key={item.path}>
                <button
                  type="button"
                  onClick={() => handleSelect(item.path)}
                  className={`flex w-full flex-col items-start gap-1 px-4 py-2 text-left text-sm transition ${
                    index === activeIndex ? "bg-brand-500/20 text-white" : "text-slate-200 hover:bg-slate-800/60"
                  }`}
                >
                  <span className="font-medium">{item.name}</span>
                  <span className="text-xs text-slate-400">{item.path}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
