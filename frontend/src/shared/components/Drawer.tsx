interface DrawerProps {
  title: string
  isOpen: boolean
  onClose: () => void
  children: React.ReactNode
}

export function Drawer({ title, isOpen, onClose, children }: DrawerProps) {
  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal>
      <div
        className="flex-1 bg-slate-900/40"
        aria-hidden
        onClick={onClose}
      />
      <aside className="h-full w-full max-w-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <span className="sr-only">Close drawer</span>
            ×
          </button>
        </div>
        <div className="h-full overflow-y-auto px-6 py-6">{children}</div>
      </aside>
    </div>
  )
}
