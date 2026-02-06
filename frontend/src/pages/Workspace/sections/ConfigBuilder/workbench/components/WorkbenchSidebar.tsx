import { useEffect, useState } from "react";
import clsx from "clsx";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { ChevronRightTinyIcon, FileIcon, FolderIcon } from "@/components/icons";

import type { WorkbenchFileNode } from "../types";

interface WorkbenchSidebarProps {
  readonly tree: WorkbenchFileNode;
  readonly activeFileId?: string;
  readonly onSelectFile: (fileId: string) => void;
  readonly configDisplayName: string;
}

function buildDefaultExpanded(nodes: readonly WorkbenchFileNode[]): Set<string> {
  const expanded = new Set<string>();
  const visit = (node: WorkbenchFileNode) => {
    if (node.kind !== "folder") {
      return;
    }
    expanded.add(node.id);
    node.children?.forEach(visit);
  };
  nodes.forEach(visit);
  return expanded;
}

function toDomId(value: string) {
  return `workbench-tree-${value.replace(/[^a-zA-Z0-9-_]/g, "-")}`;
}

export function WorkbenchSidebar({
  tree,
  activeFileId,
  onSelectFile,
  configDisplayName,
}: WorkbenchSidebarProps) {
  const labelClassName = "group-data-[collapsible=icon]:hidden";
  const menuButtonClassName = "group-data-[collapsible=icon]:justify-center";
  const topLevelNodes = tree.children ?? [];
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(() =>
    buildDefaultExpanded(topLevelNodes),
  );

  useEffect(() => {
    setExpandedFolders(buildDefaultExpanded(tree.children ?? []));
  }, [tree.id, tree.children]);

  const handleToggleFolder = (folderId: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  function renderFile(node: WorkbenchFileNode, isNested: boolean) {
    const isActive = node.id === activeFileId;
    const content = (
      <>
        <FileIcon className="h-4 w-4" />
        <span className={labelClassName}>{node.name}</span>
      </>
    );

    if (isNested) {
      return (
        <SidebarMenuSubItem key={node.id}>
          <SidebarMenuSubButton asChild isActive={isActive}>
            <button type="button" onClick={() => onSelectFile(node.id)} title={node.name}>
              {content}
            </button>
          </SidebarMenuSubButton>
        </SidebarMenuSubItem>
      );
    }

    return (
      <SidebarMenuItem key={node.id}>
        <SidebarMenuButton
          type="button"
          isActive={isActive}
          onClick={() => onSelectFile(node.id)}
          tooltip={node.name}
          className={menuButtonClassName}
        >
          {content}
        </SidebarMenuButton>
      </SidebarMenuItem>
    );
  }

  function renderChildren(children: readonly WorkbenchFileNode[]) {
    return children.map((child) =>
      child.kind === "folder" ? renderFolder(child, true) : renderFile(child, true),
    );
  }

  function renderFolder(node: WorkbenchFileNode, isNested: boolean) {
    const children = node.children ?? [];
    const hasChildren = children.length > 0;
    const isExpanded = expandedFolders.has(node.id);
    const listId = toDomId(node.id);
    const icon = (
      <ChevronRightTinyIcon
        className={clsx(
          "h-3 w-3 text-sidebar-foreground/70 transition-transform",
          isExpanded && "rotate-90",
        )}
      />
    );

    const content = (
      <>
        {icon}
        <FolderIcon className="h-4 w-4" />
        <span className={labelClassName}>{node.name}</span>
      </>
    );

    const buttonProps = {
      onClick: () => handleToggleFolder(node.id),
      "aria-expanded": hasChildren ? isExpanded : undefined,
      "aria-controls": hasChildren ? listId : undefined,
      title: node.name,
    };

    if (isNested) {
      return (
        <SidebarMenuSubItem key={node.id}>
          <SidebarMenuSubButton asChild>
            <button type="button" {...buttonProps}>{content}</button>
          </SidebarMenuSubButton>
          {hasChildren && isExpanded ? <SidebarMenuSub id={listId}>{renderChildren(children)}</SidebarMenuSub> : null}
        </SidebarMenuSubItem>
      );
    }

    return (
      <SidebarMenuItem key={node.id}>
        <SidebarMenuButton type="button" tooltip={node.name} className={menuButtonClassName} {...buttonProps}>
          {content}
        </SidebarMenuButton>
        {hasChildren && isExpanded ? <SidebarMenuSub id={listId}>{renderChildren(children)}</SidebarMenuSub> : null}
      </SidebarMenuItem>
    );
  }

  return (
    <Sidebar
      collapsible="icon"
      className="border-r border-sidebar-border md:absolute md:h-full"
    >
      <SidebarHeader className="group-data-[collapsible=icon]:hidden">
        <div className="space-y-1 rounded-md bg-sidebar-accent/40 px-2 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-sidebar-foreground/70">
            Config files
          </p>
          <p className="truncate text-sm font-semibold text-sidebar-foreground" title={configDisplayName}>
            {configDisplayName}
          </p>
        </div>
      </SidebarHeader>
      <SidebarSeparator className="group-data-[collapsible=icon]:hidden" />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Explorer</SidebarGroupLabel>
          <SidebarGroupContent>
            {topLevelNodes.length === 0 ? (
              <p className="px-2 py-3 text-xs text-sidebar-foreground/70 group-data-[collapsible=icon]:hidden">
                No files in this configuration.
              </p>
            ) : (
              <SidebarMenu>
                {topLevelNodes.map((node) =>
                  node.kind === "folder" ? renderFolder(node, false) : renderFile(node, false),
                )}
              </SidebarMenu>
            )}
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
