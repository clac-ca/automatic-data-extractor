import * as Toast from "@radix-ui/react-toast";
import { useState } from "react";

import "./toaster.css";

export function Toaster() {
  const [open, setOpen] = useState(false);

  return (
    <Toast.Provider swipeDirection="right">
      <Toast.Viewport className="ade-toast-viewport" />
      <Toast.Root
        className="ade-toast"
        open={open}
        onOpenChange={setOpen}
        duration={3000}
      >
        <Toast.Title className="ade-toast__title">Notification</Toast.Title>
        <Toast.Description className="ade-toast__description">
          TODO: Wire toast messages
        </Toast.Description>
      </Toast.Root>
    </Toast.Provider>
  );
}
