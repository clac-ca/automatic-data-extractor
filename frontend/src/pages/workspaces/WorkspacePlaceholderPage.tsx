import { Card } from "@components/Card";

export function WorkspacePlaceholderPage({ name }: { name: string }) {
  return (
    <Card>
      <h2>{name}</h2>
      <p>TODO: Implement the {name.toLowerCase()} view.</p>
    </Card>
  );
}
