import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@components/primitives/Button";
import { useToast } from "@hooks/useToast";
import { useSession } from "@hooks/useSession";

import { useSignInMutation } from "@features/auth/hooks/useSignInMutation";

import "@styles/sign-in.css";

export function SignInForm(): JSX.Element {
  const navigate = useNavigate();
  const { signIn } = useSession();
  const { pushToast } = useToast();
  const { mutateAsync, isPending } = useSignInMutation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      const result = await mutateAsync({ email, password });
      signIn(result.session);
      pushToast({ tone: "success", title: "Signed in" });
      navigate("/workspaces");
    } catch (submissionError) {
      const errorMessage =
        submissionError instanceof Error ? submissionError.message : "Sign-in failed";
      pushToast({ tone: "error", title: "Unable to sign in", description: errorMessage });
    }
  };

  return (
    <form className="sign-in-form" onSubmit={handleSubmit}>
      <div className="sign-in-form__field">
        <label className="form-control">
          <span className="form-control__label">Email</span>
          <input
            className="form-control__input"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
      </div>
      <div className="sign-in-form__field">
        <label className="form-control">
          <span className="form-control__label">Password</span>
          <input
            className="form-control__input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
      </div>
      <Button type="submit" variant="primary" size="md" disabled={isPending}>
        {isPending ? "Signing in..." : "Sign in"}
      </Button>
    </form>
  );
}
