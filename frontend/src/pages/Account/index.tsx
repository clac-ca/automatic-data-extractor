import { Navigate, useParams, useLocation } from "react-router-dom";

export default function AccountCenterScreen() {
  const params = useParams<{ "*": string }>();
  const location = useLocation();
  const rawPath = (params["*"] ?? "").trim();
  const segments = rawPath
    .split("/")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

  const targetSegment = segments[0] ?? "";

  if (targetSegment === "security") {
    return <Navigate to={`/settings/security${location.search}`} replace />;
  }
  if (targetSegment === "api-keys") {
    return <Navigate to="/settings/api-keys" replace />;
  }

  // Default to profile for overview, profile, or any legacy path
  return <Navigate to="/settings/profile" replace />;
}
