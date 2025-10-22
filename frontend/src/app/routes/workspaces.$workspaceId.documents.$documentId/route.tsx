export const handle = { workspaceSectionId: "documents" } as const;

interface DocumentRouteParams {
  readonly documentId?: string;
}

export default function DocumentDetailRoute({ params }: { readonly params: DocumentRouteParams }) {
  return (
    <section>
      <h1 className="text-lg font-semibold">Document {params.documentId}</h1>
      <p className="mt-2 text-sm text-slate-600">TODO: render document details or drawer.</p>
    </section>
  );
}
