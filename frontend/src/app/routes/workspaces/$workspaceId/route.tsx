import type { ShouldRevalidateFunctionArgs } from "react-router-dom";

import { WorkspaceLayout } from "./WorkspaceLayout";
import { workspaceLoader } from "./loader";

export { workspaceLoader as loader };

export function shouldRevalidate({ currentParams, nextParams }: ShouldRevalidateFunctionArgs) {
  return currentParams.workspaceId !== nextParams.workspaceId;
}

export default function WorkspaceRoute() {
  return <WorkspaceLayout />;
}
