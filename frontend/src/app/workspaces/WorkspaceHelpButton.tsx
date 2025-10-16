import { Button } from "../../ui";

export function WorkspaceHelpButton() {
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={() => {
        window.open("https://docs.automatic-data-extractor.example/help", "_blank", "noopener,noreferrer");
      }}
    >
      Help
    </Button>
  );
}
