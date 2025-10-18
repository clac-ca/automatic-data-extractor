import { renderToString } from "react-dom/server";
import { ServerRouter, type AppLoadContext, type EntryContext } from "react-router";

export default async function handleRequest(
  request: Request,
  status: number,
  headers: Headers,
  context: EntryContext,
  _loadContext: AppLoadContext,
) {
  const markup = renderToString(<ServerRouter context={context} url={request.url} />);
  headers.set("Content-Type", "text/html");
  return new Response(`<!DOCTYPE html>${markup}`, { status, headers });
}

