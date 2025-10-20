import type { components } from "@types/api";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Schemas[T];

export type JobStatus = "pending" | "running" | "succeeded" | "failed";

type JobRecordSchema = Schema<"JobRecord">;

export type JobRecord = Readonly<
  Omit<JobRecordSchema, "status"> & {
    status: JobStatus;
  }
>;

export type JobSubmissionPayload = Readonly<Schema<"JobSubmissionRequest">>;
