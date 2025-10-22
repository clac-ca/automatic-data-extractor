import { redirect } from "react-router";
import type { ClientActionFunctionArgs, ClientLoaderFunctionArgs } from "react-router";

import { performLogout } from "@shared/auth/api/logout";

async function logoutAndRedirect(signal: AbortSignal) {
  await performLogout({ signal });
  throw redirect("/login");
}

export function clientLoader({ request }: ClientLoaderFunctionArgs) {
  return logoutAndRedirect(request.signal);
}

export function clientAction({ request }: ClientActionFunctionArgs) {
  return logoutAndRedirect(request.signal);
}

export default function LogoutRoute() {
  return null;
}
