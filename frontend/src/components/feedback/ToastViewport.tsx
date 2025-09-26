import { useToast } from "@hooks/useToast";

import "@styles/toast.css";

export function ToastViewport(): JSX.Element | null {
  const { toasts, dismissToast } = useToast();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <div className="toast-viewport" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast--${toast.tone}`}>
          <div className="toast__content">
            <strong className="toast__title">{toast.title}</strong>
            {toast.description ? <p className="toast__description">{toast.description}</p> : null}
          </div>
          <button
            type="button"
            className="toast__close"
            aria-label="Dismiss notification"
            onClick={() => dismissToast(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
