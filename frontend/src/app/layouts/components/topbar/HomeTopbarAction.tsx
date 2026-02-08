import { House } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function HomeTopbarAction() {
  return (
    <Button asChild variant="outline" size="sm" className="h-9">
      <Link to="/" aria-label="Go to home">
        <House className="size-4" />
        <span>Home</span>
      </Link>
    </Button>
  );
}
