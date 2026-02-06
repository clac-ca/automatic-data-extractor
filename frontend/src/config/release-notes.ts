export const RELEASE_NOTES_URL = "https://github.com/clac-ca/automatic-data-extractor/releases";

export function openReleaseNotes(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.open(RELEASE_NOTES_URL, "_blank", "noopener,noreferrer");
}
