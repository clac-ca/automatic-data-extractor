import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettingsFormErrorSummary } from "../SettingsFormErrorSummary";

describe("SettingsFormErrorSummary", () => {
  it("renders linked errors", async () => {
    render(
      <SettingsFormErrorSummary
        summary={{
          title: "Fix form errors",
          items: [
            {
              key: "email",
              label: "Email",
              message: "Required",
              fieldId: "user-email",
            },
          ],
        }}
      />, 
    );

    expect(screen.getByText("Fix form errors")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Email: Required" })).toHaveAttribute(
      "href",
      "#user-email",
    );
  });

  it("returns null when summary is empty", () => {
    const { container } = render(<SettingsFormErrorSummary summary={null} />);
    expect(container.firstChild).toBeNull();
  });
});
