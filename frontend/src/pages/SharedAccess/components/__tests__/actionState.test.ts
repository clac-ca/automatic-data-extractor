import { describe, expect, it } from "vitest";

import { resolveAccessActionState } from "../actionState";

describe("resolveAccessActionState", () => {
  it("returns enabled state by default", () => {
    expect(resolveAccessActionState()).toEqual({
      disabled: false,
      reasonCode: null,
      reasonText: null,
    });
  });

  it("returns default copy for known reason codes", () => {
    const state = resolveAccessActionState({
      isDisabled: true,
      reasonCode: "provider_managed",
    });

    expect(state.disabled).toBe(true);
    expect(state.reasonCode).toBe("provider_managed");
    expect(state.reasonText).toContain("read-only");
  });
});
