import { AssignmentDetailView } from "@/components/assignments/AssignmentDetailView";

export default async function AssignmentDetailPage({
  params,
}: {
  params: Promise<{ assignmentId: string }>;
}) {
  const { assignmentId } = await params;
  return <AssignmentDetailView assignmentId={assignmentId} />;
}
