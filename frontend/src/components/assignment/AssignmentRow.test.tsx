import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssignmentRow } from "@/components/assignment/AssignmentRow";

describe("AssignmentRow", () => {
  it("renders past due time label", () => {
    render(
      <AssignmentRow
        assignment={{
          id: "a1",
          courseId: "c1",
          title: "Sample",
          dueAt: "2020-01-01T00:00:00.000Z",
          deadlineWindow: "past_due_time",
        }}
        course={{ id: "c1", name: "Course" }}
      />,
    );
    expect(screen.getByText("Past due time")).toBeInTheDocument();
  });

  it.each([
    ["2026-10-16T04:00:00.000Z", "Oct 15, 11:00 PM CDT"],
    ["2026-12-10T05:59:00.000Z", "Dec 9, 11:59 PM CST"],
  ])("shows the timezone label on the due date (%s)", (dueAt, expected) => {
    render(
      <AssignmentRow
        assignment={{ id: "a2", courseId: "c1", title: "Sample", dueAt }}
        course={{ id: "c1", name: "Course" }}
      />,
    );
    expect(screen.getByText(expected)).toBeInTheDocument();
  });
});
