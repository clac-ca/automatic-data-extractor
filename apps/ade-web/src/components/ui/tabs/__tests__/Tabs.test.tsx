import { useState } from "react";

import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { render, screen } from "@test/test-utils";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@components/ui/tabs";

function ExampleTabs() {
  const [value, setValue] = useState("one");
  return (
    <TabsRoot value={value} onValueChange={setValue}>
      <TabsList aria-label="Example tabs" className="flex gap-2">
        <TabsTrigger value="one">One</TabsTrigger>
        <TabsTrigger value="two">Two</TabsTrigger>
        <TabsTrigger value="three">Three</TabsTrigger>
      </TabsList>
      <TabsContent value="one">Panel one</TabsContent>
      <TabsContent value="two">Panel two</TabsContent>
      <TabsContent value="three">Panel three</TabsContent>
    </TabsRoot>
  );
}

describe("Tabs", () => {
  it("renders roles and selection state", () => {
    render(<ExampleTabs />);

    const tablist = screen.getByRole("tablist", { name: "Example tabs" });
    expect(tablist).toBeInTheDocument();

    const firstTab = screen.getByRole("tab", { name: "One" });
    expect(firstTab).toHaveAttribute("aria-selected", "true");

    const panel = screen.getByRole("tabpanel", { name: "One" });
    expect(panel).toHaveTextContent("Panel one");
  });

  it("supports roving focus with arrow keys", async () => {
    const user = userEvent.setup();
    render(<ExampleTabs />);

    const firstTab = screen.getByRole("tab", { name: "One" });
    const secondTab = screen.getByRole("tab", { name: "Two" });
    const thirdTab = screen.getByRole("tab", { name: "Three" });

    firstTab.focus();
    await user.keyboard("{ArrowRight}");
    expect(secondTab).toHaveAttribute("aria-selected", "true");
    expect(secondTab).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(firstTab).toHaveAttribute("aria-selected", "true");
    expect(firstTab).toHaveFocus();

    await user.keyboard("{End}");
    expect(thirdTab).toHaveAttribute("aria-selected", "true");
    expect(thirdTab).toHaveFocus();

    await user.keyboard("{Home}");
    expect(firstTab).toHaveAttribute("aria-selected", "true");
    expect(firstTab).toHaveFocus();
  });
});
