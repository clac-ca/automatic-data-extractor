import { type KeyboardEvent } from "react";
import clsx from "clsx";

import { CloseIcon, SearchIcon } from "@/components/icons";
import { Input } from "@/components/ui/input";

interface SearchFieldProps {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  readonly onSubmit?: (value: string) => void;
  readonly onClear?: () => void;
  readonly placeholder?: string;
  readonly ariaLabel?: string;
  readonly className?: string;
  readonly inputClassName?: string;
  readonly disabled?: boolean;
}

export function SearchField({
  value,
  onValueChange,
  onSubmit,
  onClear,
  placeholder = "Search...",
  ariaLabel,
  className,
  inputClassName,
  disabled = false,
}: SearchFieldProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter" || !onSubmit) return;
    event.preventDefault();
    onSubmit(value);
  };

  const handleClear = () => {
    if (!value) return;
    onValueChange("");
    onClear?.();
  };

  return (
    <div className={clsx("relative w-full", className)}>
      <SearchIcon
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        type="search"
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
        disabled={disabled}
        className={clsx("pl-9 pr-9", inputClassName)}
      />
      {value ? (
        <button
          type="button"
          onClick={handleClear}
          className="absolute right-2 top-1/2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label="Clear search"
        >
          <CloseIcon className="h-3.5 w-3.5" />
        </button>
      ) : null}
    </div>
  );
}
