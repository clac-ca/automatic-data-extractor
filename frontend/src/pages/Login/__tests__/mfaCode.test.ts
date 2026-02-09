import { describe, expect, it } from "vitest";

import {
  buildMfaInputError,
  formatRecoveryCode,
  parseMfaCode,
} from "@/pages/Login/mfaCode";

describe("mfaCode helpers", () => {
  it("detects OTP codes and marks complete only at 6 digits", () => {
    const parsed = parseMfaCode("123456");
    expect(parsed.kind).toBe("otp");
    expect(parsed.displayValue).toBe("123456");
    expect(parsed.submitValue).toBe("123456");
    expect(parsed.isComplete).toBe(true);
  });

  it("detects recovery code shapes and formats to XXXX-XXXX", () => {
    const parsed = parseMfaCode("ab12-3cd4xx");
    expect(parsed.kind).toBe("recovery");
    expect(parsed.displayValue).toBe("AB12-3CD4");
    expect(parsed.submitValue).toBe("AB12-3CD4");
    expect(parsed.isComplete).toBe(true);
  });

  it("returns unknown for ambiguous seven-digit numeric input", () => {
    const parsed = parseMfaCode("1234567");
    expect(parsed.kind).toBe("unknown");
    expect(parsed.isComplete).toBe(false);
  });

  it("formats recovery code helper output", () => {
    expect(formatRecoveryCode("ab12-3cd4")).toBe("AB12-3CD4");
  });

  it("builds strict input errors for incomplete or invalid shapes", () => {
    const parsed = parseMfaCode("12345");
    expect(buildMfaInputError(parsed)).toBe(
      "Enter a 6-digit authenticator code or an 8-character recovery code.",
    );
  });
});
