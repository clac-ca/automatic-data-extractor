import { Form, redirect, useNavigation } from "react-router";
import type { ClientActionFunctionArgs } from "react-router";
import { useEffect, useRef } from "react";

import { ApiError } from "@shared/api";
import { client } from "@shared/api/client";

export async function clientAction({ request }: ClientActionFunctionArgs) {
  try {
    await client.DELETE("/api/v1/auth/session", { signal: request.signal });
  } catch (error) {
    if (!(error instanceof ApiError && (error.status === 401 || error.status === 403))) {
      if (import.meta.env.DEV) {
        console.warn("Failed to terminate session", error);
      }
    }
  }

  throw redirect("/login");
}

export default function LogoutRoute() {
  const navigation = useNavigation();
  const formRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    formRef.current?.submit();
  }, []);

  const isSubmitting = navigation.state === "submitting";

  return (
    <Form
      method="post"
      replace
      ref={formRef}
      className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600"
    >
      <noscript>
        <button type="submit">Sign out</button>
      </noscript>
      {isSubmitting ? "Signing you out…" : "Signed out"}
    </Form>
  );
}
