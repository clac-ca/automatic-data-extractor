import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState
} from "react";

export type ToastTone = "info" | "success" | "warning" | "error";

export interface ToastOptions {
  readonly title: string;
  readonly description?: string;
  readonly tone?: ToastTone;
  readonly timeoutMs?: number;
}

export interface Toast extends ToastOptions {
  readonly id: string;
  readonly tone: ToastTone;
  readonly timeoutMs?: number;
}

interface ToastContextValue {
  readonly toasts: Toast[];
  readonly pushToast: (options: ToastOptions) => string;
  readonly dismissToast: (id: string) => void;
  readonly clearToasts: () => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

interface ToastProviderProps {
  readonly children: ReactNode;
}

const DEFAULT_TIMEOUT = 6_000;

let toastSequence = 0;

export function ToastProvider({ children }: ToastProviderProps): JSX.Element {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, number>());

  const clearTimer = useCallback((id: string) => {
    const timerId = timers.current.get(id);
    if (timerId) {
      window.clearTimeout(timerId);
      timers.current.delete(id);
    }
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    clearTimer(id);
  }, [clearTimer]);

  const scheduleDismiss = useCallback(
    (id: string, timeoutMs?: number) => {
      if (!timeoutMs) {
        return;
      }

      clearTimer(id);
      const timerId = window.setTimeout(() => {
        dismissToast(id);
      }, timeoutMs);
      timers.current.set(id, timerId);
    },
    [dismissToast, clearTimer]
  );

  const pushToast = useCallback(
    (options: ToastOptions) => {
      const id = `toast-${Date.now()}-${toastSequence++}`;
      const tone = options.tone ?? "info";
      const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT;
      const toast: Toast = { ...options, id, tone, timeoutMs };
      setToasts((current) => [...current, toast]);
      scheduleDismiss(id, timeoutMs);
      return id;
    },
    [scheduleDismiss]
  );

  const clearToasts = useCallback(() => {
    timers.current.forEach((timerId) => window.clearTimeout(timerId));
    timers.current.clear();
    setToasts([]);
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({ toasts, pushToast, dismissToast, clearToasts }),
    [toasts, pushToast, dismissToast, clearToasts]
  );

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>;
}

export function useToastContext(): ToastContextValue {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error("useToastContext must be used within a ToastProvider");
  }

  return context;
}
