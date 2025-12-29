const MENU_ICON_CLASS = "h-4 w-4 text-current opacity-80";

export function PinGlyph({ filled }: { readonly filled: boolean }) {
  return filled ? (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="currentColor"
        className="text-muted-foreground"
      />
    </svg>
  ) : (
    <svg className="h-3 w-3" viewBox="0 0 16 16" aria-hidden>
      <path
        d="M6.5 2.5h3l.5 4h2v1.5h-4V13l-1-.5V8H4V6.5h2z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
        className="text-muted-foreground"
      />
    </svg>
  );
}

export function TabSavingSpinner() {
  return (
    <svg className="h-3 w-3 animate-spin text-brand-500" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.2" opacity="0.3" />
      <path
        d="M14 8a6 6 0 0 0-6-6"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function MenuIconSave() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M4 2.5h7.5L13.5 5v8.5H4z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 2.5v4h4v-4" stroke="currentColor" strokeWidth="1.2" />
      <path d="M6 11h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIconSaveAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5h6l3 3v5.5h-9z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
      <path d="M6 3.5v3.5h3.5v-3.5" stroke="currentColor" strokeWidth="1.2" />
      <path d="M5 11h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path
        d="M6.5 6.5h6l1.5 1.5v4"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        opacity="0.6"
      />
    </svg>
  );
}

export function MenuIconClose() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M4 4l8 8m0-8l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIconCloseOthers() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <rect x="2.5" y="3" width="8" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.2" fill="none" />
      <path d="M7 7l5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIconCloseRight() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path d="M5 3v10" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M7 5l5 3-5 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 6v4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIconCloseAll() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 4h3a1 1 0 0 1 1 1v7.5M12.5 12h-3a1 1 0 0 1-1-1V3.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M5 6l6 6m0-6-6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function MenuIconPin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5.5 2.5h5l.5 4h2v1.5h-4V13l-1-.5V8h-3V6.5h3z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export function MenuIconUnpin() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M3.5 3.5l9 9M5.5 2.5h5l.5 4h2v1.5H10M8 8v4.5L7 12.5V8H4V6.5h1"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export function MenuIconFile() {
  return (
    <svg className={MENU_ICON_CLASS} viewBox="0 0 16 16" aria-hidden>
      <path
        d="M5 2.5h4l2.5 2.5V13.5H5z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}

export function ChevronLeftIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChevronDownIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 16 16" aria-hidden>
      <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
