import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ShieldUser, Users } from "lucide-react";
import { describe, expect, it } from "vitest";

import { OrganizationSettingsTopbarSearch } from "@/pages/OrganizationSettings/components/OrganizationSettingsTopbarSearch";
import type { OrganizationSettingsNavGroup } from "@/pages/OrganizationSettings/settingsNav";

const navGroups: OrganizationSettingsNavGroup[] = [
  {
    id: "identity",
    label: "Identity",
    items: [
      {
        id: "identity.users",
        group: "identity",
        label: "Users",
        shortLabel: "Users",
        description: "Manage user accounts and access status.",
        icon: Users,
        href: "/organization/settings/users",
        canView: true,
        canEdit: true,
      },
      {
        id: "identity.roles",
        group: "identity",
        label: "Roles",
        shortLabel: "Roles",
        description: "Define global roles and permission bundles.",
        icon: ShieldUser,
        href: "/organization/settings/roles",
        canView: true,
        canEdit: true,
      },
    ],
  },
];

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location-path">{location.pathname}</span>;
}

describe("OrganizationSettingsTopbarSearch", () => {
  it("navigates to the selected section", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/organization/settings/users"]}>
        <Routes>
          <Route
            path="/organization/settings/*"
            element={
              <>
                <OrganizationSettingsTopbarSearch navGroups={navGroups} />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    const input = screen.getByLabelText("Search organization settings sections");
    await user.click(input);
    await user.type(input, "roles");
    await user.click(screen.getByText("Roles"));

    expect(screen.getByTestId("location-path")).toHaveTextContent("/organization/settings/roles");
  });

  it("only shows sections present in nav groups", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/organization/settings/users"]}>
        <Routes>
          <Route
            path="/organization/settings/*"
            element={
              <OrganizationSettingsTopbarSearch
                navGroups={[
                  {
                    ...navGroups[0],
                    items: [navGroups[0].items[0]],
                  },
                ]}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    const input = screen.getByLabelText("Search organization settings sections");
    await user.click(input);
    await user.type(input, "roles");

    expect(screen.queryByText("Roles")).not.toBeInTheDocument();
    expect(screen.getByText("No matching sections")).toBeInTheDocument();
  });
});
