# 09-workbench-editor-and-scripting

**Purpose:** Deep dive into the IDE-like Config Builder workbench: layout, file tree, tabs, console, URL state, and ADE script helpers.

### 1. Overview

* Workbench is an “editor window” that can be docked/maximised.
* Reused concepts: `WorkbenchWindow`, console, validation pane.

### 2. Workbench window states

* **Restored**:

  * Embedded in Config Builder section.

* **Maximised**:

  * Full viewport overlay, workspace shell dimmed.

* **Docked / minimised**:

  * Hidden, with a dock UI to restore.

* Controls:

  * Minimise/maximise/close buttons.
  * Unsaved-changes behaviour and blockers.

### 3. Layout and panels

* **Activity bar**:

  * Modes: explorer, search (future), SCM (future), extensions (future), settings.

* **Explorer panel**:

  * File tree, iconography, context menu.

* **Editor area**:

  * Tab strip (pinned & unpinned tabs).
  * Code editor.

* **Bottom panel**:

  * Tabs: Console, Validation.

* **Inspector panel**:

  * Metadata: size, modifiedAt, contentType, ETag.
  * Load status and dirty state.

* Resize behaviour and persistence of panel sizes.

### 4. File tree model

* Types:

  * `WorkbenchFileKind`, `WorkbenchFileMetadata`, `WorkbenchFileNode`.

* Building from backend listing:

  * Using a flat `FileListing` with `path`, `name`, `kind`, `depth`.
  * `createWorkbenchTreeFromListing`.
  * Folder creation, path normalisation, sorting (folders first).

* Helper functions:

  * `extractName`, `deriveParent`, `findFileNode`, `findFirstFile`.

### 5. Tabs, content, and persistence

* `WorkbenchFileTab` fields:

  * `id`, `name`, `language`, `initialContent`, `content`, `status`, `etag`, `pinned`, `saving`, `saveError`, `lastSavedAt`.

* `useWorkbenchFiles` hook responsibilities:

  * Open/close tabs.
  * MRU order and keyboard navigation.
  * Lazy content loading & dirty tracking.
  * Save flow and ETag concurrency handling.

* Persistence:

  * `PersistedWorkbenchTabs` structure.
  * LocalStorage key: `ade.ui.workspace.<workspaceId>.config.<configId>.tabs`.

### 6. Workbench URL state

* Types:

  * `ConfigBuilderTab`, `ConfigBuilderPane`, `ConfigBuilderConsole`, `ConfigBuilderView`, `ConfigBuilderSearchState`.

* `readConfigBuilderSearch`:

  * Parsing from URL, normalising, tracking `present` flags.

* `mergeConfigBuilderSearch`:

  * How patches are applied and defaults removed from the URL.

* `useWorkbenchUrlState`:

  * API: `fileId`, `pane`, `console`, `consoleExplicit`, setters.
  * Strategy for preferring URL vs persisted state when both exist.

### 7. Console and validation panels

* **Console**:

  * Receives build and run events from NDJSON streams.
  * Shows log text and a run summary card.

* **Validation**:

  * Structured issues (severity, path, message).
  * Populated from validation endpoint results.

* Persistence:

  * `ConsolePanelPreferences` (`version`, `fraction`, `state`).
  * Key: `ade.ui.workspace.<workspaceId>.config.<configId>.console`.

### 8. Editor and theme preference

* `CodeEditor` component:

  * Props: `language`, `path`, `theme`, `readOnly`, `onSaveShortcut`.
  * `CodeEditorHandle` (focus + revealLine).

* Theme preference:

  * `EditorThemePreference` (`system` | `light` | `dark`).
  * `EditorThemeId` (`ade-dark`, `vs-light`).
  * LocalStorage key: `ade.ui.workspace.<workspaceId>.config.<configId>.editor-theme`.
  * System dark/light detection.

### 9. ADE script helpers and script API

* `registerAdeScriptHelpers`:

  * Scope detection based on file paths (`row_detectors`, `column_detectors`, `hooks`).
  * Features: hover docs, completions, signature help.

* Expected function signatures:

  * Row detectors.
  * Column detectors.
  * Transforms.
  * Validators.
  * Hooks (`on_job_start`, `after_mapping`, `before_save`, `on_job_end`).

* Note: helpers are guidance only, not enforcement of backend behaviour.
