"""Guards for source coverage and the semantic boundary experiment."""

import io

from adaptive_chunking import anchor_span, covered, semantic_spans, text_pdf
from pypdf import PdfReader


class TopicVectors:
    """Controlled distances to test splitting; real E5 is used in measurements."""

    def embed(self, texts, role):
        return [[1.0, 0.0] if "Identity" in text else [0.0, 1.0] for text in texts]


def test_topic_change_keeps_one_sentence_of_context_and_all_source():
    first = "Identity permissions remain restricted. " * 16
    second = "Archive copies remain encrypted. " * 16
    text = first + second
    spans = semantic_spans(text, TopicVectors())
    assert len(spans) == 2
    assert spans[0] == (0, len(first))
    assert spans[1][0] == len(first) - len("Identity permissions remain restricted. ")
    assert spans[1][1] == len(text)


def test_long_unbroken_sentence_is_bounded_and_preserved():
    text = "ż" * 4200
    spans = semantic_spans(text, TopicVectors())
    assert all(b - a <= 1800 for a, b in spans)
    assert covered(text, [{"start": a, "end": b} for a, b in spans], (0, len(text)))
    assert semantic_spans("", TopicVectors()) == []


def test_rule_alone_does_not_count_as_exception_coverage():
    text = "Delete records in 20 days. Internal process. Except records under legal hold."
    rule = anchor_span(text, "Delete records in 20 days.")
    exception = anchor_span(text, "Except records under legal hold.")
    selected = [{"start": 0, "end": 26}]
    assert covered(text, selected, rule)
    assert not covered(text, selected, exception)
    selected.append({"start": 44, "end": len(text)})
    assert covered(text, selected, exception)


def test_wrapping_and_real_pdf_preserve_queryable_text():
    text = "Delete records\nin 20 days.\nExcept records under legal hold.\n"
    raw = text_pdf(text)
    extracted = PdfReader(io.BytesIO(raw)).pages[0].extract_text()
    assert anchor_span(extracted, "Delete records in 20 days.")
    assert anchor_span(extracted, "Except records under legal hold.")


def test_line_break_after_literal_hyphen_does_not_hide_anchor():
    assert anchor_span("Use non-\ninteractive identities.", "non-interactive identities.") == (
        4,
        32,
    )
