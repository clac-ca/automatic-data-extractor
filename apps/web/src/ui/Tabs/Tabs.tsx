import {
  createContext,
  useContext,
  useId,
  useMemo,
  type HTMLAttributes,
  type PropsWithChildren,
  type ButtonHTMLAttributes,
} from "react";

interface TabsContextValue {
  readonly value: string;
  readonly setValue: (value: string) => void;
  readonly baseId: string;
}

const TabsContext = createContext<TabsContextValue | null>(null);

export interface TabsRootProps extends PropsWithChildren {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
}

export function TabsRoot({ value, onValueChange, children }: TabsRootProps) {
  const baseId = useId();
  const contextValue = useMemo(
    () => ({ value, setValue: onValueChange, baseId }),
    [value, onValueChange, baseId],
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

export function TabsTrigger({ value, children, className, onClick, disabled, ...rest }: TabsTriggerProps) {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error("TabsTrigger must be used within a TabsRoot");
  }

  const selected = context.value === value;
  const id = `${context.baseId}-tab-${value}`;
  const panelId = `${context.baseId}-panel-${value}`;

  return (
    <button
      {...rest}
      type="button"
      role="tab"
      id={id}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      className={className}
      disabled={disabled}
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
