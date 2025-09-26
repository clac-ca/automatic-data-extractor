import { Navigate } from "react-router-dom";

import { SignInForm } from "@features/auth/components/SignInForm";
import { useSession } from "@hooks/useSession";

import "@styles/sign-in-page.css";

export function SignInPage(): JSX.Element {
  const { isAuthenticated } = useSession();

  if (isAuthenticated) {
    return <Navigate to="/workspaces" replace />;
  }

  return (
    <div className="sign-in-page">
      <div className="sign-in-page__panel">
        <h1 className="sign-in-page__title">Automatic Data Extractor</h1>
        <p className="sign-in-page__subtitle">
          Upload documents, launch extraction jobs, and review structured results in a single workspace.
        </p>
        <SignInForm />
      </div>
      <div className="sign-in-page__aside" aria-hidden="true">
        <div className="sign-in-page__gradient" />
        <div className="sign-in-page__aside-content">
          <h2>Deterministic document extraction</h2>
          <p>
            ADE keeps extraction logic versioned and auditable so analysts and reviewers can trust every table delivered to stakeholders.
          </p>
        </div>
      </div>
    </div>
  );
}
