import * as React from "react"
import { Search as SearchIcon } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  SearchDialog,
  SearchEmpty,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
} from "@/components/ui/search"
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext"

export function WorkspaceSearch() {
  const navigate = useNavigate()
  const { workspace } = useWorkspaceContext()
  const [open, setOpen] = React.useState(false)

  const base = `/workspaces/${workspace.id}`
  const items = [
    { key: "documents", label: "Documents", to: `${base}/documents` },
    { key: "runs", label: "Runs", to: `${base}/runs` },
    {
      key: "config-builder",
      label: "Config Builder",
      to: `${base}/config-builder`,
      keywords: ["config", "builder"],
    },
    { key: "settings", label: "Settings", to: `${base}/settings` },
  ]

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className="w-full justify-start text-muted-foreground"
        onClick={() => setOpen(true)}
      >
        <SearchIcon className="size-4" aria-hidden="true" />
        Search workspace...
      </Button>

      <SearchDialog open={open} onOpenChange={setOpen}>
        <SearchInput placeholder="Search workspace..." autoFocus />
        <SearchList>
          <SearchEmpty>No results.</SearchEmpty>
          <SearchGroup heading="Navigation">
            {items.map((item) => (
              <SearchItem
                key={item.key}
                value={item.label}
                keywords={item.keywords}
                onSelect={() => {
                  navigate(item.to)
                  setOpen(false)
                }}
              >
                {item.label}
              </SearchItem>
            ))}
          </SearchGroup>
        </SearchList>
      </SearchDialog>
    </>
  )
}
