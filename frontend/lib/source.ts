import type { Citation, DocumentRecord } from "@/lib/types";

export function sourceHref(citation: Citation): string {
  // Fragments keep source quotations out of HTTP requests and server logs.
  const fragment = new URLSearchParams({
    chunk: citation.chunk_id,
    quote: citation.quote,
  });
  return `/documents/${encodeURIComponent(citation.document_id)}#${fragment}`;
}

function matches(text: string, quote: string): RegExpExecArray[] {
  const pattern = quote.trim().split(/\s+/)
    .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("\\s+");
  if (!pattern) return [];
  const regex = new RegExp(pattern, "g");
  const first = regex.exec(text);
  if (!first) return [];
  // A second match, including an overlapping one, makes the location ambiguous.
  regex.lastIndex = first.index + 1;
  const second = regex.exec(text);
  return second ? [first, second] : [first];
}

export function locateSource(
  document: DocumentRecord,
  chunkId: string | null,
  quote: string | null,
): { start?: number; end?: number; notice?: string } {
  if (!quote?.trim()) {
    return chunkId ? {
      notice: "This older source link has no exact quote to highlight. Read the full document below.",
    } : {};
  }
  if (!document.text) {
    return { notice: "The full source text is unavailable, so the quote cannot be highlighted." };
  }
  const chunk = document.chunks?.find((item) => item.id === chunkId);
  if (!chunk) {
    return { notice: "The source anchor is unavailable. No quote has been highlighted." };
  }
  const anchors = matches(document.text, chunk.text);
  if (anchors.length !== 1) {
    return { notice: anchors.length
      ? "Multiple matching source passages were found. An exact location cannot be highlighted reliably."
      : "The cited passage could not be located in the full document. No quote has been highlighted." };
  }
  const quotes = matches(anchors[0][0], quote);
  if (quotes.length !== 1) {
    return { notice: quotes.length
      ? "The quote occurs more than once in the cited passage. An exact location cannot be highlighted reliably."
      : "The cited quote could not be found in its source passage. No quote has been highlighted." };
  }
  const start = anchors[0].index + quotes[0].index;
  return { start, end: start + quotes[0][0].length };
}
