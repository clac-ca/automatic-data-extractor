import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { render } from "@test/test-utils";
import type { WorkbenchFileNode } from "../../types";
import { Explorer } from "../Explorer";

function buildTree(): WorkbenchFileNode {
  return {
    id: "",
    name: "",
    kind: "folder",
    children: [
      {
        id: "src",
        name: "src",
        kind: "folder",
        children: [],
      },
    ],
  };
}

describe("Explorer", () => {
  it("creates folders from the context menu", async () => {
    const onCreateFolder = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canCreateFile
        canCreateFolder
        isCreatingEntry={false}
        onCreateFolder={onCreateFolder}
        onCreateFile={vi.fn()}
        canDeleteFile={false}
        canDeleteFolder={false}
        onCloseFile={() => {}}
        onCloseOtherFiles={() => {}}
        onCloseTabsToRight={() => {}}
        onCloseAllFiles={() => {}}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    fireEvent.contextMenu(folderButton, { clientX: 10, clientY: 10 });

    const menu = await screen.findByRole("menu");
    const newFolderItem = within(menu).getByRole("menuitem", { name: /New Folder/i });
    await user.click(newFolderItem);

    const input = await screen.findByPlaceholderText("new_folder");
    await user.type(input, "nested{enter}");

    expect(onCreateFolder).toHaveBeenCalledWith("src", "nested");
  });

  it("creates files from the context menu", async () => {
    const onCreateFile = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canCreateFile
        canCreateFolder
        isCreatingEntry={false}
        onCreateFolder={vi.fn()}
        onCreateFile={onCreateFile}
        canDeleteFile={false}
        canDeleteFolder={false}
        onCloseFile={() => {}}
        onCloseOtherFiles={() => {}}
        onCloseTabsToRight={() => {}}
        onCloseAllFiles={() => {}}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    fireEvent.contextMenu(folderButton, { clientX: 12, clientY: 12 });

    const menu = await screen.findByRole("menu");
    const newFileItem = within(menu).getByRole("menuitem", { name: /New File/i });
    await user.click(newFileItem);

    const input = await screen.findByPlaceholderText("new_file.py");
    await user.type(input, "example.py{enter}");

    expect(onCreateFile).toHaveBeenCalledWith("src", "example.py");
  });

  it("triggers folder deletion from the context menu", async () => {
    const onDeleteFolder = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canCreateFile
        canCreateFolder
        isCreatingEntry={false}
        onCreateFolder={vi.fn()}
        onCreateFile={vi.fn()}
        canDeleteFile
        canDeleteFolder
        onDeleteFolder={onDeleteFolder}
        onCloseFile={() => {}}
        onCloseOtherFiles={() => {}}
        onCloseTabsToRight={() => {}}
        onCloseAllFiles={() => {}}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    fireEvent.contextMenu(folderButton, { clientX: 20, clientY: 20 });

    const menu = await screen.findByRole("menu");
    const deleteFolderItem = within(menu).getByRole("menuitem", { name: /Delete Folder/i });
    await user.click(deleteFolderItem);

    expect(onDeleteFolder).toHaveBeenCalledWith("src");
  });
});
