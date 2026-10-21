"use client";

import React, { memo } from "react";

interface AcademicMarkdownViewProps {
  content: string;
  className?: string;
}

// Convert common LaTeX math tokens to readable unicode and formatted HTML
function renderMathString(mathStr: string): React.ReactNode {
  // Clean outer delimiters
  let text = mathStr.trim();
  if (text.startsWith("$$") && text.endsWith("$$")) {
    text = text.slice(2, -2).trim();
  } else if (text.startsWith("$") && text.endsWith("$")) {
    text = text.slice(1, -1).trim();
  }

  // Replace common Greek letters
  const greekMap: Record<string, string> = {
    "\\theta": "θ",
    "\\Theta": "Θ",
    "\\pi": "π",
    "\\Pi": "Π",
    "\\alpha": "α",
    "\\beta": "β",
    "\\gamma": "γ",
    "\\Gamma": "Γ",
    "\\lambda": "λ",
    "\\Lambda": "Λ",
    "\\sigma": "σ",
    "\\omega": "ω",
    "\\Omega": "Ω",
    "\\phi": "φ",
    "\\delta": "δ",
    "\\Delta": "Δ",
    "\\epsilon": "ε",
  };

  for (const [tex, unicode] of Object.entries(greekMap)) {
    text = text.replaceAll(tex, unicode);
  }

  // Replace operators
  text = text
    .replaceAll("\\times", " × ")
    .replaceAll("\\cdot", " · ")
    .replaceAll("\\pm", " ± ")
    .replaceAll("\\leq", " ≤ ")
    .replaceAll("\\geq", " ≥ ")
    .replaceAll("\\neq", " ≠ ")
    .replaceAll("\\approx", " ≈ ")
    .replaceAll("\\degree", "°")
    .replaceAll("^{\\circ}", "°")
    .replaceAll("^\\circ", "°")
    .replaceAll("\\to", " → ")
    .replaceAll("\\rightarrow", " → ");

  // Handle \frac{a}{b} -> (a / b)
  text = text.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1 / $2)");

  // Split by subscripts and superscripts
  // Tokenize into text, sub, sup
  const parts: React.ReactNode[] = [];
  const tokenRegex = /([_|\^])(?:\{([^{}]+)\}|([0-9a-zA-Z°]+))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = tokenRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const isSub = match[1] === "_";
    const val = match[2] || match[3];
    if (isSub) {
      parts.push(
        <sub key={`sub-${match.index}`} className="text-[0.75em] bottom-[-0.2em] relative">
          {val}
        </sub>
      );
    } else {
      parts.push(
        <sup key={`sup-${match.index}`} className="text-[0.75em] top-[-0.3em] relative">
          {val}
        </sup>
      );
    }
    lastIndex = tokenRegex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return (
    <span className="font-serif tracking-tight text-[var(--foreground)] font-medium inline-flex items-baseline px-0.5">
      {parts}
    </span>
  );
}

// Render inline formatting: math ($...$), code (`...`), bold (**...**), italic (*...*)
function renderInlineFormatting(line: string): React.ReactNode {
  // Regex pattern matching:
  // 1. Math: $(.+?)\$
  // 2. Code: `([^`]+)`
  // 3. Bold: \*\*(.+?)\*\*
  // 4. Italic: \*([^*]+)\*
  const pattern = /(\$[^$]+\$|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  const tokens = line.split(pattern);

  return tokens.map((token, index) => {
    if (!token) return null;

    if (token.startsWith("$") && token.endsWith("$") && token.length > 2) {
      return (
        <span
          key={index}
          className="inline-block rounded px-1 py-0.5 bg-[var(--surface-muted)] text-[var(--accent)] font-mono text-[0.9em] border border-[var(--border)] mx-0.5"
        >
          {renderMathString(token)}
        </span>
      );
    }

    if (token.startsWith("`") && token.endsWith("`") && token.length > 1) {
      return (
        <code
          key={index}
          className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5 font-mono text-xs text-[var(--accent)] border border-[var(--border)]"
        >
          {token.slice(1, -1)}
        </code>
      );
    }

    if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
      return (
        <strong key={index} className="font-semibold text-[var(--foreground)]">
          {token.slice(2, -2)}
        </strong>
      );
    }

    if (token.startsWith("*") && token.endsWith("*") && token.length > 2) {
      return (
        <em key={index} className="italic text-[var(--foreground)]">
          {token.slice(1, -1)}
        </em>
      );
    }

    // Auto-detect math equations even if unescaped: e.g. "theta1 + theta2", "L1*cos(θ1)"
    if (/(?:θ[0-9]|theta[0-9]|cos\(|sin\(|L[0-9]\s*\*)/i.test(token)) {
      return (
        <span key={index} className="font-mono text-[0.92em]">
          {renderMathString(token)}
        </span>
      );
    }

    return token;
  });
}

export const AcademicMarkdownView = memo(function AcademicMarkdownView({
  content,
  className = "",
}: AcademicMarkdownViewProps) {
  if (!content) return null;

  // Split into lines
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let currentList: { type: "ul" | "ol"; items: React.ReactNode[] } | null = null;

  const flushList = () => {
    if (!currentList) return;
    const ListTag = currentList.type;
    blocks.push(
      <ListTag
        key={`list-${blocks.length}`}
        className={`my-2 space-y-1.5 pl-5 ${
          currentList.type === "ul" ? "list-disc marker:text-[var(--accent)]" : "list-decimal marker:text-[var(--muted)]"
        }`}
      >
        {currentList.items.map((item, idx) => (
          <li key={idx} className="text-sm leading-relaxed text-[var(--foreground)]">
            {item}
          </li>
        ))}
      </ListTag>
    );
    currentList = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Fenced code block handling
    if (trimmed.startsWith("```")) {
      flushList();
      if (inCodeBlock) {
        blocks.push(
          <pre
            key={`code-${blocks.length}`}
            className="my-3 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface-muted)] p-3 text-xs font-mono text-[var(--foreground)]"
          >
            <code>{codeBuffer.join("\n")}</code>
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(rawLine);
      continue;
    }

    // Display math: $$ ... $$
    if (trimmed.startsWith("$$") && trimmed.endsWith("$$") && trimmed.length > 4) {
      flushList();
      blocks.push(
        <div
          key={`math-block-${blocks.length}`}
          className="my-3 overflow-x-auto rounded-xl border border-[var(--border)] bg-[var(--surface-muted)]/50 p-3 text-center"
        >
          <div className="text-sm sm:text-base">{renderMathString(trimmed)}</div>
        </div>
      );
      continue;
    }

    // Empty line
    if (!trimmed) {
      flushList();
      continue;
    }

    // Headers
    if (trimmed.startsWith("### ")) {
      flushList();
      blocks.push(
        <h4 key={`h4-${blocks.length}`} className="mt-3 mb-1 text-sm font-semibold tracking-tight text-[var(--foreground)]">
          {renderInlineFormatting(trimmed.slice(4))}
        </h4>
      );
      continue;
    }
    if (trimmed.startsWith("## ")) {
      flushList();
      blocks.push(
        <h3 key={`h3-${blocks.length}`} className="mt-4 mb-1.5 text-base font-semibold tracking-tight text-[var(--foreground)]">
          {renderInlineFormatting(trimmed.slice(3))}
        </h3>
      );
      continue;
    }
    if (trimmed.startsWith("# ")) {
      flushList();
      blocks.push(
        <h2 key={`h2-${blocks.length}`} className="mt-4 mb-2 text-lg font-bold tracking-tight text-[var(--foreground)]">
          {renderInlineFormatting(trimmed.slice(2))}
        </h2>
      );
      continue;
    }

    // Unordered list items: • or - or *
    if (trimmed.startsWith("• ") || trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const itemText = trimmed.slice(2);
      if (!currentList || currentList.type !== "ul") {
        flushList();
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push(renderInlineFormatting(itemText));
      continue;
    }

    // Ordered list items: 1. , 2. , etc.
    const orderedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (orderedMatch) {
      const itemText = orderedMatch[2];
      if (!currentList || currentList.type !== "ol") {
        flushList();
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push(renderInlineFormatting(itemText));
      continue;
    }

    // Standalone equation line: starts with "x =" or "y =" or parameter list
    if (/^[xy]\s*=\s*/i.test(trimmed) || trimmed.startsWith("• Link") || trimmed.startsWith("• Joint")) {
      flushList();
      blocks.push(
        <div
          key={`eq-${blocks.length}`}
          className="my-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface-muted)]/30 px-3 py-1.5 font-mono text-xs sm:text-sm text-[var(--foreground)]"
        >
          {renderInlineFormatting(trimmed)}
        </div>
      );
      continue;
    }

    // Normal paragraph
    flushList();
    blocks.push(
      <p key={`p-${blocks.length}`} className="my-1 text-sm leading-relaxed text-[var(--foreground)] break-words">
        {renderInlineFormatting(trimmed)}
      </p>
    );
  }

  flushList();

  return <div className={`academic-markdown space-y-1 ${className}`}>{blocks}</div>;
});
