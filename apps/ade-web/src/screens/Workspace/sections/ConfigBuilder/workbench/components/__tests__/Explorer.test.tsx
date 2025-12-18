import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(() => {
  window.localStorage.clear();
});

describe("Explorer", () => {
  it("uploads dropped files into a folder target", async () => {
    const onUploadFiles = vi.fn();
    const file = new File(["hello"], "example.py", { type: "text/x-python" });

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canUploadFiles
        onUploadFiles={onUploadFiles}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    fireEvent.drop(folderButton, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
        items: [],
      },
    });

    await waitFor(() => {
      expect(onUploadFiles).toHaveBeenCalledWith("src", [{ file, relativePath: "example.py" }]);
    });
  });

  it("uploads dropped files using the parent folder when dropped on a file", async () => {
    const tree: WorkbenchFileNode = {
      id: "",
      name: "",
      kind: "folder",
      children: [
        {
          id: "src",
          name: "src",
          kind: "folder",
          children: [
            {
              id: "src/foo.py",
              name: "foo.py",
              kind: "file",
            },
          ],
        },
      ],
    };

    const onUploadFiles = vi.fn();
    const file = new File(["hello"], "bar.py", { type: "text/x-python" });
    const user = userEvent.setup();

    render(
      <Explorer
        width={300}
        tree={tree}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canUploadFiles
        onUploadFiles={onUploadFiles}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    await user.click(folderButton);

    const fileButton = screen.getByRole("button", { name: "foo.py" });
    fireEvent.drop(fileButton, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
        items: [],
      },
    });

    await waitFor(() => {
      expect(onUploadFiles).toHaveBeenCalledWith("src", [{ file, relativePath: "bar.py" }]);
    });
  });

  it("ignores drop uploads when uploads are disabled", async () => {
    const onUploadFiles = vi.fn();
    const file = new File(["hello"], "example.py", { type: "text/x-python" });

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        canUploadFiles={false}
        onUploadFiles={onUploadFiles}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    fireEvent.drop(folderButton, {
      dataTransfer: {
        types: ["Files"],
        files: [file],
        items: [],
      },
    });

    await waitFor(() => {
      expect(onUploadFiles).not.toHaveBeenCalled();
    });
  });

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

  it("restores expanded folders from storage", () => {
    const storageKey = "test.explorer.expanded.restore";
    window.localStorage.setItem(storageKey, JSON.stringify(["src"]));

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        expandedStorageKey={storageKey}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    expect(folderButton).toHaveAttribute("aria-expanded", "true");
  });

  it("persists folder expansion changes to storage", async () => {
    const storageKey = "test.explorer.expanded.persist";
    const user = userEvent.setup();

    render(
      <Explorer
        width={300}
        tree={buildTree()}
        activeFileId=""
        openFileIds={[]}
        onSelectFile={() => {}}
        theme="light"
        expandedStorageKey={storageKey}
        onHide={() => {}}
      />,
    );

    const folderButton = screen.getByRole("button", { name: "src" });
    expect(folderButton).toHaveAttribute("aria-expanded", "false");

    await user.click(folderButton);

    await waitFor(() => {
      expect(window.localStorage.getItem(storageKey)).toBe(JSON.stringify(["src"]));
    });
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
