import type { RouteObject } from "react-router-dom";
import { SetupRoute } from "./SetupRoute";
import { RequireSetupIncomplete } from "../../../app/guards";

export const setupRoutes: RouteObject[] = [
  {
    path: "/setup",
    element: <RequireSetupIncomplete />,
    children: [{ index: true, element: <SetupRoute /> }],
  },
];
