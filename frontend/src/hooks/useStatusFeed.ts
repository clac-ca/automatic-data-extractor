import { useStatusContext } from "@app/providers/StatusProvider";

export function useStatusFeed() {
  return useStatusContext();
}
