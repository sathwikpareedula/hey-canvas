import { DocumentDetailView } from "@/components/materials/DocumentDetailView";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return <DocumentDetailView documentId={documentId} />;
}
