/** SSE frame parser for POST /api/assistant/stream (text/event-stream). */

export interface AssistantSseEvent {
  event: string;
  data: Record<string, unknown>;
}

export class AssistantSseDecoder {
  private buffer = "";
  private readonly decoder = new TextDecoder("utf-8", { fatal: false });

  push(chunk: Uint8Array | string): AssistantSseEvent[] {
    const text = typeof chunk === "string" ? chunk : this.decoder.decode(chunk, { stream: true });
    this.buffer += text;
    return this.drainCompleteFrames();
  }

  flush(): AssistantSseEvent[] {
    const tail = this.decoder.decode();
    if (tail) this.buffer += tail;
    const frames = this.drainCompleteFrames();
    if (this.buffer.trim()) {
      const partial = parseSseFrame(this.buffer);
      if (partial) frames.push(partial);
      this.buffer = "";
    }
    return frames;
  }

  private drainCompleteFrames(): AssistantSseEvent[] {
    const out: AssistantSseEvent[] = [];
    let splitAt = this.buffer.indexOf("\n\n");
    while (splitAt !== -1) {
      const raw = this.buffer.slice(0, splitAt);
      this.buffer = this.buffer.slice(splitAt + 2);
      const parsed = parseSseFrame(raw);
      if (parsed) out.push(parsed);
      splitAt = this.buffer.indexOf("\n\n");
    }
    return out;
  }
}

export function parseSseFrame(raw: string): AssistantSseEvent | null {
  const lines = raw.split(/\r?\n/);
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  const joined = dataLines.join("\n");
  try {
    const data = JSON.parse(joined) as Record<string, unknown>;
    return { event: eventName, data };
  } catch {
    return null;
  }
}
