"""Guard the new PDF rendition against altered source punctuation."""

from adaptive_chunking import anchor_span, source_pages
from long_contracts import contract_pdf
from retrieval_comparison import amendment_spans, select_context


def test_pdf_preserves_apostrophes_across_pages(tmp_path):
    quote = "Northstar's authenticated request starts Cedar's export deadline."
    path = tmp_path / "contract.pdf"
    path.write_bytes(contract_pdf("\n" * 44 + quote.replace(" starts ", " starts\n")))
    pages = source_pages(path)
    assert len(pages) == 2
    text = "\n".join(p for p, _ in pages)
    start, end = anchor_span(text, quote)
    assert " ".join(text[start:end].split()) == quote


def test_amendment_context_is_bounded_and_does_not_swallow_next_section():
    text = "## Service\n\nSee the amendment for a changed deadline.\n\n## Addendum B\n\nDelete after seven days.\n\n## Billing\n\nInvoices follow a separate schedule."
    spans = amendment_spans(text)
    assert len(spans) == 1
    assert "seven days" in text[slice(*spans[0])]
    assert "Invoices" not in text[slice(*spans[0])]
    chunks = [
        {"id": "baseline", "text": "x" * 1800, "start": 0, "end": 10},
        {"id": "other", "text": "y" * 1800, "start": 10, "end": 20},
        {
            "id": "amendment",
            "text": "z" * 900,
            "start": spans[0][0],
            "end": spans[0][1],
        },
    ]
    selected = select_context(chunks, "amendment", 3000, spans)
    assert {c["id"] for c in selected} == {"baseline", "amendment"}
    assert sum(len(c["text"]) for c in selected) <= 3000
    assert len({c["id"] for c in selected}) == len(selected)


def test_prose_mention_of_amendment_is_not_a_section():
    assert (
        amendment_spans(
            "An amendment might change the deadline.\n\nNo amendment is signed."
        )
        == []
    )
