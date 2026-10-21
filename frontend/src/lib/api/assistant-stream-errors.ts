/** Map backend SSE error text to student-facing copy (keep retry hints). */

export function presentAssistantStreamError(message: string): string {
  const lower = message.trim().toLowerCase();
  if (!lower || lower === "network error") {
    return (
      "Hey Canvas lost the connection while your local AI was answering. " +
      "Wait for any other answers to finish, then retry."
    );
  }
  if (lower.includes("local ai is already answering")) {
    return message;
  }
  if (lower.includes("ollama") || lower.includes("local ai")) {
    return message;
  }
  if (lower.includes("provider request failed") || lower.includes("provider unavailable")) {
    return (
      "Hey Canvas could not reach your local AI (Ollama). " +
      "Confirm it is running, then retry."
    );
  }
  if (lower.includes("assistant provider returned invalid")) {
    return "The local AI returned an unexpected response. Please retry.";
  }
  return message;
}
