import { useCallback, useEffect, useMemo, useState } from "react";
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
  const topLevelNodes = useMemo(() => tree.children ?? [], [tree.children]);
  const [expanded, setExpanded] = useState<Set<string>>(() => buildDefaultExpanded(topLevelNodes));

  useEffect(() => {
    setExpanded(buildDefaultExpanded(topLevelNodes));
  }, [tree.id, topLevelNodes]);

  const toggleFolder = useCallback((folderId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  }, []);

  const renderFile = useCallback(
    (node: WorkbenchFileNode, nested: boolean) => {
      const isActive = node.id === activeFileId;
      const content = (
        <>
          <FileIcon className="h-4 w-4" />
          <span>{node.name}</span>
        </>
      );

      if (nested) {
        return (
          <SidebarMenuSubItem key={node.id}>
            <SidebarMenuSubButton asChild isActive={isActive}>
              <button type="button" onClick={() => onSelectFile(node.id)}>
                {content}
              </button>
            </SidebarMenuSubButton>
          </SidebarMenuSubItem>
        );
      }

      return (
        <SidebarMenuItem key={node.id}>
          <SidebarMenuButton type="button" isActive={isActive} onClick={() => onSelectFile(node.id)}>
            {content}
          </SidebarMenuButton>
        </SidebarMenuItem>
      );
    },
    [activeFileId, onSelectFile],
  );

  const renderFolder = useCallback(
    (node: WorkbenchFileNode, nested: boolean) => {
      const children = node.children ?? [];
      const hasChildren = children.length > 0;
      const isExpanded = expanded.has(node.id);
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
          <span>{node.name}</span>
        </>
      );

      const buttonProps = {
        type: "button" as const,
        onClick: () => toggleFolder(node.id),
        "aria-expanded": hasChildren ? isExpanded : undefined,
        "aria-controls": hasChildren ? listId : undefined,
      };

      if (nested) {
        return (
          <SidebarMenuSubItem key={node.id}>
            <SidebarMenuSubButton asChild>
              <button {...buttonProps}>{content}</button>
            </SidebarMenuSubButton>
            {hasChildren && isExpanded ? (
              <SidebarMenuSub id={listId}>
                {children.map((child) =>
                  child.kind === "folder" ? renderFolder(child, true) : renderFile(child, true),
                )}
              </SidebarMenuSub>
            ) : null}
          </SidebarMenuSubItem>
        );
      }

      return (
        <SidebarMenuItem key={node.id}>
          <SidebarMenuButton type="button" {...buttonProps}>
            {content}
          </SidebarMenuButton>
          {hasChildren && isExpanded ? (
            <SidebarMenuSub id={listId}>
              {children.map((child) =>
                child.kind === "folder" ? renderFolder(child, true) : renderFile(child, true),
              )}
            </SidebarMenuSub>
          ) : null}
        </SidebarMenuItem>
      );
    },
    [expanded, renderFile, toggleFolder],
  );

  return (
    <Sidebar collapsible="none" className="border-r border-sidebar-border">
      <SidebarHeader>
        <div className="space-y-1 rounded-md bg-sidebar-accent/40 px-2 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-sidebar-foreground/70">
            Config files
          </p>
          <p className="truncate text-sm font-semibold text-sidebar-foreground" title={configDisplayName}>
            {configDisplayName}
          </p>
        </div>
      </SidebarHeader>
      <SidebarSeparator />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Explorer</SidebarGroupLabel>
          <SidebarGroupContent>
            {topLevelNodes.length === 0 ? (
              <p className="px-2 py-3 text-xs text-sidebar-foreground/70">No files in this configuration.</p>
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
