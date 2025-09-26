import { Link } from "react-router-dom";

import { EmptyState } from "@components/layout/EmptyState";
import { Button } from "@components/primitives/Button";

export function NotFoundPage(): JSX.Element {
  return (
    <EmptyState
      title="Page not found"
      description="The page you are looking for does not exist."
      action={
        <Link to="/workspaces">
          <Button variant="primary" size="sm">
            Go to workspaces
          </Button>
        </Link>
      }
    />
  );
}
