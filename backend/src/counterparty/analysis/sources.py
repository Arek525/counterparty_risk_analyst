"""Source coordinates, ordering and exact-quote grounding shared by analysis pipelines."""

from .schemas import quote_matches, validate_source


def source(chunk: dict, quote: str) -> dict:
    return {
        "chunk_id": str(chunk["id"]),
        "document_id": str(chunk["document_id"]),
        "location": chunk["location"],
        "quote": quote,
    }


def source_order(chunks: list[dict]) -> list[dict]:
    """Group documents without letting retrieval rank become source order."""

    def key(chunk):
        location = chunk.get("location", {})
        coordinates = (
            (location.get("page", 0), location.get("line_start", 0), location.get("line_end", 0))
            if isinstance(location, dict)
            else (0, 0, 0)
        )
        return str(chunk["document_id"]), *coordinates, str(chunk["id"])

    return sorted(chunks, key=key)


def ground_model_sources(items: list[dict], batch: list[dict]) -> int:
    """Restore source coordinates and whitespace only for uniquely grounded literal words."""
    corrections = 0
    for item in items:
        citation = item["source"]
        try:
            validate_source(citation, batch)
        except ValueError:
            matches = quote_matches(
                citation["quote"],
                [chunk for chunk in batch if str(chunk["document_id"]) == citation["document_id"]],
                normalize_whitespace=True,
            )
            if len(matches) != 1:
                raise
            anchor, quote = matches[0]
            corrected = {
                **citation,
                "chunk_id": str(anchor["id"]),
                "location": anchor["location"],
                "quote": quote,
            }
            validate_source(corrected, batch)
            item["source"] = corrected
            corrections += 1
    return corrections
