import { BrowserRouter } from "react-router-dom";

import { AppRouter } from "@app/routing/AppRouter";

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  );
}
