"use client"

import * as React from "react"
import type { DialogProps } from "@radix-ui/react-dialog"
import { Command as CommandPrimitive } from "cmdk"
import { Search as SearchIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Dialog, DialogContent } from "@/components/ui/dialog"

/* -----------------------------------------------------------------------------
 * Search (foundation)
 *
 * What this file is:
 * - A thin, styled wrapper around cmdk primitives for building search UIs
 * - A small Dialog convenience for “command palette” style search
 *
 * What this file is NOT:
 * - A fetch/caching/pagination framework
 * - A results renderer with data models
 * ---------------------------------------------------------------------------*/

export type SearchProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive>

export const Search = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  SearchProps
>(({ className, label = "Search", ...props }, ref) => (
  <CommandPrimitive
    ref={ref}
    label={label}
    data-slot="search"
    className={cn(
      "flex w-full flex-col overflow-hidden rounded-md bg-popover text-popover-foreground",
      className
    )}
    {...props}
  />
))
Search.displayName = "Search"

export interface SearchDialogProps extends DialogProps {
  /**
   * Props forwarded to the underlying <Search /> (cmdk <Command />).
   * This is the escape hatch for advanced cases (e.g. shouldFilter={false}).
   *
   * Inspired by the shadcn CommandDialog “commandProps” pattern.
   */
  searchProps?: SearchProps
  /**
   * Local extension: allow sizing the dialog content without re-implementing SearchDialog.
   */
  contentClassName?: string
}

export function SearchDialog({
  children,
  searchProps,
  contentClassName,
  ...props
}: SearchDialogProps) {
  const { className: searchClassName, ...restSearchProps } = searchProps ?? {}

  return (
    <Dialog {...props}>
      <DialogContent className={cn("overflow-hidden p-0 shadow-lg", contentClassName)}>
        <Search
          // Dialog-specific sizing like shadcn CommandDialog (easy to tweak).
          className={cn(
            "[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground",
            "[&_[cmdk-group]:not([hidden])_~[cmdk-group]]:pt-0 [&_[cmdk-group]]:px-2",
            "[&_[cmdk-input-wrapper]_svg]:h-5 [&_[cmdk-input-wrapper]_svg]:w-5",
            "[&_[cmdk-input]]:h-12",
            "[&_[cmdk-item]]:px-2 [&_[cmdk-item]]:py-3 [&_[cmdk-item]_svg]:h-5 [&_[cmdk-item]_svg]:w-5",
            searchClassName
          )}
          {...restSearchProps}
        >
          {children}
        </Search>
      </DialogContent>
    </Dialog>
  )
}

export type SearchInputProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>

export const SearchInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  SearchInputProps
>(({ className, placeholder = "Search…", autoComplete = "off", autoCorrect = "off", spellCheck = false, ...props }, ref) => (
  <div
    data-slot="search-input-wrapper"
    // cmdk selectors rely on this in many shadcn-style implementations.
    cmdk-input-wrapper=""
    className="flex items-center gap-2 border-b border-border px-3"
  >
    <SearchIcon className="size-4 shrink-0 opacity-50" aria-hidden="true" />
    <CommandPrimitive.Input
      ref={ref}
      data-slot="search-input"
      placeholder={placeholder}
      autoComplete={autoComplete}
      autoCorrect={autoCorrect}
      spellCheck={spellCheck}
      className={cn(
        "flex h-11 w-full bg-transparent py-3 text-sm outline-none",
        "placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  </div>
))
SearchInput.displayName = "SearchInput"

export type SearchListProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>

export const SearchList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  SearchListProps
>(({ className, ...props }, ref) => (
  <CommandPrimitive.List
    ref={ref}
    data-slot="search-list"
    className={cn(
      "max-h-[300px] overflow-y-auto overflow-x-hidden p-1",
      className
    )}
    {...props}
  />
))
SearchList.displayName = "SearchList"

export type SearchEmptyProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>

export const SearchEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  SearchEmptyProps
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Empty
    ref={ref}
    data-slot="search-empty"
    className={cn("py-6 text-center text-sm text-muted-foreground", className)}
    {...props}
  />
))
SearchEmpty.displayName = "SearchEmpty"

export type SearchGroupProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>

export const SearchGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  SearchGroupProps
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Group
    ref={ref}
    data-slot="search-group"
    className={cn(
      "overflow-hidden p-1 text-foreground",
      "[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5",
      "[&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted-foreground",
      className
    )}
    {...props}
  />
))
SearchGroup.displayName = "SearchGroup"

export type SearchSeparatorProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.Separator>

export const SearchSeparator = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Separator>,
  SearchSeparatorProps
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Separator
    ref={ref}
    data-slot="search-separator"
    className={cn("-mx-1 h-px bg-border", className)}
    {...props}
  />
))
SearchSeparator.displayName = "SearchSeparator"

export type SearchItemProps = React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>

export const SearchItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  SearchItemProps
>(({ className, ...props }, ref) => (
  <CommandPrimitive.Item
    ref={ref}
    data-slot="search-item"
    className={cn(
      "relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none",
      "aria-selected:bg-accent aria-selected:text-accent-foreground",
      // IMPORTANT: use value-based selectors (not presence selectors).
      // Presence selectors can match `"false"` and effectively “disable everything”.
      "data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50",
      "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
      className
    )}
    {...props}
  />
))
SearchItem.displayName = "SearchItem"

export function SearchShortcut({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      data-slot="search-shortcut"
      className={cn("ml-auto text-xs tracking-widest text-muted-foreground", className)}
      {...props}
    />
  )
}
