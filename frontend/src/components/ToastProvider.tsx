import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ToastTone = "info" | "success" | "error";

export interface ToastOptions {
  title: string;
  description?: string;
  tone?: ToastTone;
}

interface Toast extends ToastOptions {
  id: number;
  tone: ToastTone;
}

interface ToastContextValue {
  pushToast: (options: ToastOptions) => number;
  dismissToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismissToast = useCallback((id: number) => {
    setToasts((items) => items.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    ({ title, description, tone = "info" }: ToastOptions) => {
      const id = Date.now() + Math.random();
      setToasts((items) => [
        ...items,
        {
          id,
          title,
          description,
          tone,
        },
      ]);
      return id;
    },
    [],
  );

  const value = useMemo(
    () => ({ pushToast, dismissToast }),
    [pushToast, dismissToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`}>
            <div className="toast-content">
              <div className="toast-text">
                <p className="toast-title">{toast.title}</p>
                {toast.description ? (
                  <p className="toast-description">{toast.description}</p>
                ) : null}
              </div>
              <button
                type="button"
                className="toast-dismiss"
                onClick={() => dismissToast(toast.id)}
              >
                <span className="sr-only">Dismiss notification</span>
                ×
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
