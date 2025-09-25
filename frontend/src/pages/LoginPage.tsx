import { Button } from "@components/Button";
import { Card } from "@components/Card";
import { Page } from "@components/Page";

export function LoginPage() {
  return (
    <Page
      title="Login"
      description="Authenticate with the ADE backend to access your workspaces."
      actions={<Button>TODO: Sign in</Button>}
    >
      <Card>
        <p>
          TODO: Replace this placeholder with the actual authentication form once the auth feature is
          scheduled.
        </p>
      </Card>
    </Page>
  );
}
