import { useQuery } from "@tanstack/react-query";

import { listConfigTemplates } from "../api";
import { configTemplateKeys } from "../keys";
import type { ConfigTemplate } from "../types";

export function useConfigTemplatesQuery() {
  return useQuery<ConfigTemplate[]>({
    queryKey: configTemplateKeys.list(),
    queryFn: ({ signal }) => listConfigTemplates(signal),
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}
