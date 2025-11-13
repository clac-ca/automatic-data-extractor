import {
  createContext,
  useCallback,
  useContext,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  type HTMLAttributes,
  type PropsWithChildren,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
} from "react";

interface TabsContextValue {
  readonly value: string;
  readonly setValue: (value: string) => void;
  readonly baseId: string;
  readonly registerValue: (value: string, element: HTMLButtonElement | null) => void;
  readonly unregisterValue: (value: string) => void;
  readonly focusValue: (value: string | undefined) => void;
  readonly getValues: () => string[];
}

const TabsContext = createContext<TabsContextValue | null>(null);

export interface TabsRootProps extends PropsWithChildren {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
}

export function TabsRoot({ value, onValueChange, children }: TabsRootProps) {
  const baseId = useId();
  const valuesRef = useRef<string[]>([]);
  const nodesRef = useRef(new Map<string, HTMLButtonElement | null>());

  const registerValue = useCallback((val: string, element: HTMLButtonElement | null) => {
    if (!valuesRef.current.includes(val)) {
      valuesRef.current.push(val);
    }
    nodesRef.current.set(val, element);
  }, []);

  const unregisterValue = useCallback((val: string) => {
    valuesRef.current = valuesRef.current.filter((entry) => entry !== val);
    nodesRef.current.delete(val);
  }, []);

  const focusValue = useCallback((val: string | undefined) => {
    if (!val) {
      return;
    }
    nodesRef.current.get(val)?.focus();
  }, []);

  const getValues = useCallback(() => valuesRef.current.slice(), []);

  const contextValue = useMemo(
    () => ({
      value,
      setValue: onValueChange,
      baseId,
      registerValue,
      unregisterValue,
      focusValue,
      getValues,
    }),
    [value, onValueChange, baseId, registerValue, unregisterValue, focusValue, getValues],
  );

  return <TabsContext.Provider value={contextValue}>{children}</TabsContext.Provider>;
}

export function TabsList({ children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div role="tablist" {...rest}>
      {children}
    </div>
  );
}

export interface TabsTriggerProps extends PropsWithChildren, ButtonHTMLAttributes<HTMLButtonElement> {
  readonly value: string;
}

export function TabsTrigger({ value, children, className, onClick, onKeyDown, disabled, ...rest }: TabsTriggerProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("TabsTrigger must be used within a TabsRoot");
  }

  const { registerValue, unregisterValue, focusValue, getValues } = context;
  const selected = context.value === value;
  const id = `${context.baseId}-tab-${value}`;
  const panelId = `${context.baseId}-panel-${value}`;

  const setButtonRef = useCallback(
    (node: HTMLButtonElement | null) => {
      registerValue(value, node);
    },
    [registerValue, value],
  );

  useLayoutEffect(() => () => unregisterValue(value), [unregisterValue, value]);

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    onKeyDown?.(event);
    if (event.defaultPrevented) {
      return;
    }

    const values = getValues();
    const currentIndex = values.indexOf(value);
    if (currentIndex === -1 || values.length === 0) {
      return;
    }

    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") {
      event.preventDefault();
      nextIndex = (currentIndex + 1) % values.length;
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      nextIndex = (currentIndex - 1 + values.length) % values.length;
    } else if (event.key === "Home") {
      event.preventDefault();
      nextIndex = 0;
    } else if (event.key === "End") {
      event.preventDefault();
      nextIndex = values.length - 1;
    }

    const nextValue = values[nextIndex];
    if (nextValue && nextValue !== context.value) {
      context.setValue(nextValue);
    }
    focusValue(nextValue);
  };

  return (
    <button
      {...rest}
      ref={setButtonRef}
      type="button"
      role="tab"
      id={id}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      className={className}
      disabled={disabled}
      onKeyDown={handleKeyDown}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented && !disabled) {
          context.setValue(value);
        }
      }}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps extends PropsWithChildren, HTMLAttributes<HTMLDivElement> {
  readonly value: string;
}

export function TabsContent({ value, children, className, ...rest }: TabsContentProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("TabsContent must be used within a TabsRoot");
  }

  const selected = context.value === value;
  const id = `${context.baseId}-panel-${value}`;
  const tabId = `${context.baseId}-tab-${value}`;

  return (
    <div
      {...rest}
      role="tabpanel"
      id={id}
      aria-labelledby={tabId}
      className={className}
      hidden={!selected}
      tabIndex={0}
    >
      {children}
    </div>
  );
}
