"""Bounded text ingestion with immutable originals and source coordinates."""

import hashlib
import io
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from counterparty.models import Document, DocumentChunk, User

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500_000
MAX_PAGES = 300
CHUNK_CHARS = 1800


def safe_filename(value: str) -> str:
    name = re.split(r"[/\\]", value)[-1]
    name = re.sub(r"[^\w .()-]", "_", name, flags=re.UNICODE).strip(" .")
    return name[:240] or "document.txt"


def original_text(document: Document, storage_path: str) -> str:
    path = Path(storage_path) / document.storage_key
    if not path.is_file():
        raise HTTPException(404, "Original file unavailable")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != document.sha256:
        raise HTTPException(409, "Original document integrity check failed")
    if document.media_type == "application/pdf":
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
    return raw.decode("utf-8-sig")


def extract(raw: bytes, filename: str) -> tuple[list[dict], str]:
    suffix = Path(filename).suffix.lower()
    pages = []
    if suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise HTTPException(422, "Invalid PDF signature")
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise HTTPException(422, "Encrypted PDFs are unsupported")
            if len(reader.pages) > MAX_PAGES:
                raise HTTPException(422, "PDF page limit exceeded")
            total = 0
            for index, page in enumerate(reader.pages):
                # Bound decompressed content before expensive text extraction.
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > MAX_UPLOAD_BYTES:
                    raise HTTPException(422, "PDF page content limit exceeded")
                value = page.extract_text() or ""
                total += len(value)
                if total > MAX_TEXT_CHARS:
                    raise HTTPException(422, "Extracted text limit exceeded")
                if not value.strip():
                    raise HTTPException(
                        422, "PDF contains a scan or empty page; OCR is unsupported"
                    )
                pages.append((value, {"page": index + 1}))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(422, "Unable to extract PDF text") from exc
        media_type = "application/pdf"
    elif suffix in {".md", ".txt"}:
        try:
            value = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(422, "Text documents must use UTF-8") from exc
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise HTTPException(422, "Binary content is not a text document")
        pages = [(value, {})]
        media_type = "text/markdown" if suffix == ".md" else "text/plain"
    else:
        raise HTTPException(422, "Supported extensions: .pdf, .md, .txt")
    if sum(len(value) for value, _ in pages) > MAX_TEXT_CHARS:
        raise HTTPException(422, "Extracted text limit exceeded")
    chunks = []
    for value, base in pages:
        # Chunk complete lines when possible, and split exceptionally long lines.
        lines = value.splitlines(keepends=True)
        buffer = ""
        start = 1
        for number, line in enumerate(lines, 1):
            if buffer and len(buffer) + len(line) > CHUNK_CHARS:
                if buffer.strip():
                    chunks.append(
                        {
                            "text": buffer.strip(),
                            "location": {**base, "line_start": start, "line_end": number - 1},
                        }
                    )
                buffer = ""
                start = number
            while len(line) > CHUNK_CHARS:
                part, line = line[:CHUNK_CHARS], line[CHUNK_CHARS:]
                if part.strip():
                    chunks.append(
                        {
                            "text": part.strip(),
                            "location": {**base, "line_start": number, "line_end": number},
                        }
                    )
            if not buffer:
                start = number
            buffer += line
        if buffer.strip():
            chunks.append(
                {
                    "text": buffer.strip(),
                    "location": {**base, "line_start": start, "line_end": len(lines)},
                }
            )
    if not chunks:
        raise HTTPException(422, "Document contains no extractable text; OCR is unsupported")
    return chunks, media_type


def read_upload(file: UploadFile) -> bytes:
    buffer = bytearray()
    while block := file.file.read(64 * 1024):
        buffer.extend(block)
        if len(buffer) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Document exceeds the 10 MiB limit")
    if not buffer:
        raise HTTPException(422, "Empty document")
    return bytes(buffer)


def ingest(
    session: Session,
    user: User,
    raw: bytes,
    filename: str,
    kind: str,
    case_id: UUID | None,
    storage_path: str,
    evidence_type: str = "declaration",
) -> tuple[Document, bool]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Document exceeds the 10 MiB limit")
    filename = safe_filename(filename)
    digest = hashlib.sha256(raw).hexdigest()
    # One scope lock prevents concurrent hash duplicates and version races.
    scope = f"documents:{user.organization_id}:{case_id}:{kind}"
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"), {"scope": scope}
    )
    query = select(Document).where(
        Document.organization_id == user.organization_id,
        Document.case_id == case_id,
        Document.kind == kind,
    )
    existing = session.scalar(query.where(Document.sha256 == digest))
    if existing:
        return existing, False
    chunks, media_type = extract(raw, filename)
    version = (
        session.scalar(
            select(func.max(Document.version)).where(
                Document.organization_id == user.organization_id,
                Document.case_id == case_id,
                Document.kind == kind,
                Document.filename == filename,
            )
        )
        or 0
    ) + 1
    document_id = uuid4()
    key = f"{user.organization_id}/{document_id}/{digest}"
    target = Path(storage_path) / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    session.info.setdefault("new_document_paths", []).append(target)
    document = Document(
        id=document_id,
        organization_id=user.organization_id,
        case_id=case_id,
        uploaded_by=user.id,
        kind=kind,
        filename=filename,
        evidence_type=evidence_type,
        sha256=digest,
        storage_key=key,
        version=version,
        media_type=media_type,
    )
    session.add(document)
    try:
        session.flush()
        for chunk in chunks:
            session.add(
                DocumentChunk(
                    document_id=document.id,
                    organization_id=user.organization_id,
                    case_id=case_id,
                    text=chunk["text"],
                    location=chunk["location"],
                )
            )
        session.flush()
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return document, True


def chunk_dict(chunk: DocumentChunk, document: Document) -> dict:
    return {
        "id": str(chunk.id),
        "document_id": str(document.id),
        "text": chunk.text,
        "location": chunk.location,
        "kind": document.kind,
        "filename": document.filename,
        "document_version": document.version,
        "document_sha256": document.sha256,
        "embedding_model": chunk.embedding_model,
        "evidence_type": document.evidence_type,
    }


# File storage participates in the unit of work: failed bootstrap/upload transactions
# remove their newly created originals. Committed references survive session cleanup.
from sqlalchemy import event  # noqa: E402


@event.listens_for(Session, "after_rollback")
def remove_rolled_back_originals(session):
    for path in session.info.pop("new_document_paths", []):
        path.unlink(missing_ok=True)


@event.listens_for(Session, "after_commit")
def forget_committed_originals(session):
    session.info.pop("new_document_paths", None)


def chunks_for(session, documents):
    result = []
    for document in documents:
        chunks = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.id)
        ).all()
        # Source order is stable even though chunk UUIDs are random.
        chunks = sorted(
            chunks, key=lambda c: (c.location.get("page", 0), c.location.get("line_start", 0))
        )
        result.extend(chunk_dict(chunk, document) for chunk in chunks)
    return result
