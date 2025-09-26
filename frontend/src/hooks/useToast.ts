import { useToastContext } from "@app/providers/ToastProvider";

export function useToast() {
  return useToastContext();
}
