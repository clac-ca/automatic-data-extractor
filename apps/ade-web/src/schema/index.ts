// Curated, app-facing types re-exported from the generated OpenAPI definitions.
// Prefer importing from this module instead of referencing the raw generated file.
import type {
  components as GeneratedComponents,
  paths as GeneratedPaths,
  operations as GeneratedOperations,
} from "@generated-types/openapi";

// Base OpenAPI maps. Useful when you need to index into components or paths directly.
export type components = GeneratedComponents;
export type paths = GeneratedPaths;
export type operations = GeneratedOperations;

// Frequently used schema fragments. Extend this list as new app-level contracts emerge.
export type SessionEnvelope = GeneratedComponents["schemas"]["SessionEnvelope"];
export type SetupStatus = GeneratedComponents["schemas"]["SetupStatus"];
export type SetupRequest = GeneratedComponents["schemas"]["SetupRequest"];
export type UserProfile = GeneratedComponents["schemas"]["UserProfile"];
export type RunResource = GeneratedComponents["schemas"]["RunResource"];
export type RunStatus = RunResource["status"];
export type RunCreateOptions = GeneratedComponents["schemas"]["RunCreateOptions"];
export type { ArtifactV1 } from "./adeArtifact";
