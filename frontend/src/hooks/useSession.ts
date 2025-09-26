import { useSessionContext } from "@app/providers/SessionProvider";

export function useSession() {
  return useSessionContext();
}
