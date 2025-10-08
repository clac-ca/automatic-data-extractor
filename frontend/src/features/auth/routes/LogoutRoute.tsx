import { useEffect } from "react";

import { useLogoutMutation } from "../hooks/useLogoutMutation";

export function LogoutRoute() {
  const { mutate } = useLogoutMutation();

  useEffect(() => {
    mutate();
  }, [mutate]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-slate-300">
      Signing you out…
    </div>
  );
}
