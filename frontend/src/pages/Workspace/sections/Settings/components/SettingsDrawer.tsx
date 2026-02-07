import clsx from "clsx";
import type { ReactNode } from "react";

import * as DialogPrimitive from "@radix-ui/react-dialog";

import { CloseIcon } from "@/components/icons";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogDescription,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/ui/dialog";

interface SettingsDrawerProps {
  readonly open: boolean;
  readonly title: string;
  readonly description?: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly widthClassName?: string;
}

export function SettingsDrawer({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  widthClassName = "w-full max-w-xl",
}: SettingsDrawerProps) {
  return (
    <Dialog open={open} onOpenChange={(next) => (!next ? onClose() : undefined)}>
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          aria-label={title}
          className={clsx(
            "fixed inset-y-0 right-0 left-auto top-0 z-[var(--app-z-modal)] flex h-full w-full min-h-0 flex-col gap-0 overflow-hidden rounded-none border-l bg-card p-0 shadow-2xl",
            "data-[state=closed]:slide-out-to-right-2 data-[state=open]:slide-in-from-right-2 data-[state=closed]:animate-out data-[state=open]:animate-in",
            widthClassName,
          )}
        >
          <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-border bg-card/95 px-4 py-4 backdrop-blur sm:px-6">
            <div className="space-y-1">
              <DialogTitle className="text-lg font-semibold text-foreground">{title}</DialogTitle>
              {description ? (
                <DialogDescription className="text-sm text-muted-foreground">
                  {description}
                </DialogDescription>
              ) : null}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={onClose}
              aria-label="Close drawer"
              className="text-muted-foreground"
            >
              <CloseIcon className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">{children}</div>

          {footer ? (
            <>
              <Separator />
              <div className="sticky bottom-0 z-10 bg-card/95 px-4 py-4 backdrop-blur sm:px-6">{footer}</div>
            </>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPortal>
    </Dialog>
  );
}
