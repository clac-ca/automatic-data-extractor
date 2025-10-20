# User Guide

This guide explains how business users will interact with the Automatic Data Extractor (ADE) once the web experience is live. The frontend is still in design, but the core concepts are locked in. By understanding the workflow now, you will be ready to adopt the product the moment the interface ships.

## ADE in a nutshell

ADE turns messy spreadsheets and PDFs into clean tables that you can trust. Every action in the interface revolves around three objects:

1. **Documents** – the files you upload for extraction.
2. **Jobs** – the processing runs that transform a document into structured data.

The frontend groups features around this lifecycle so that you can easily follow a document from upload to completion.

## Getting ready

Before you sign in for the first time, make sure you have:

- **Workspace access** – your administrator will invite you to the workspace that contains your documents.
- **Source files** – the spreadsheets or PDFs you plan to process. ADE works best with tabular layouts that follow a consistent template from file to file.
- **Destination plan** – decide how you want to consume the extracted tables (e.g., CSV download, business intelligence tools, or API hand-off).

When the frontend launches you will receive a welcome email with your login link and initial password. After you sign in, the home screen walks you through uploading your first document.

## Uploading documents

The upload flow is designed to be friendly for non-technical users:

1. Choose **Upload document** from the dashboard.
2. Drag and drop files or browse to select them from your computer.
3. Optionally label the document with tags (such as reporting period or client name) so that it is easier to find later.
4. Confirm the workspace destination and submit.

ADE immediately checks that the file type is supported and starts the extraction run right away. Most documents finish in seconds, and the interface streams progress so you can keep working while ADE processes the file.

## Monitoring extraction jobs

Every upload creates a job card that shows live status updates:

- **Pending** – ADE is preparing the extraction run.
- **Running** – the parsing logic is executing. Open the card to view live progress checkpoints.
- **Succeeded** – processing finished successfully and metrics are available.
- **Failed** – ADE detected an issue (for example, an unreadable table) and needs your input to resolve it.

Notification settings let you choose whether to receive email alerts when jobs finish or require attention.

## Managing history and collaboration

The activity timeline shows who uploaded each document, when extractions ran, and who viewed the outputs. Use filters to isolate a particular client, reporting period, or workspace.

Team collaboration features include:

- Shared workspaces so colleagues can pick up where you left off.
- Permissions that limit who can delete documents or rerun jobs.
- Audit logs for every action to satisfy regulatory requirements.

## What’s next

While the frontend is still in development, the workflows above will remain stable. If you want to automate uploads or integrate ADE into an existing system today, read the [API Guide](../reference/api-guide.md) for developer-focused instructions. Otherwise, keep this guide handy—the UI will mirror these concepts, making onboarding quick for you and your team.
