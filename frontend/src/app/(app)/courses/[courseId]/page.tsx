import { CourseWorkspace } from "@/components/courses/CourseWorkspace";

export default async function CoursePage({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  return <CourseWorkspace courseId={courseId} />;
}
