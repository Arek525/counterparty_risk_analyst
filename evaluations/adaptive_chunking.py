"""Paired formatting experiment with frozen fixtures; no application writes or LLM calls."""

# ruff: noqa: E501 -- Preserve complete authored source paragraphs and anchors.

import argparse
import hashlib
import io
import json
import re
import statistics
import textwrap
import time
from itertools import pairwise
from pathlib import Path

import numpy as np
from chunking_comparison import structured_spans
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from counterparty.documents import CHUNK_CHARS, extract
from counterparty.embedding_config import FINGERPRINT
from counterparty.embeddings import LocalEmbedder

ROOT = Path(__file__).resolve().parent
ORGANIZATIONS = [
    ("Aster", "en", "development", "payroll hosting", 20, 12),
    ("Orion", "pl", "development", "obsługa zgłoszeń klientów", 30, 24),
    ("Meridian", "en", "confirmation", "warehouse analytics", 14, 8),
    ("Brzeg", "pl", "confirmation", "archiwizacja umów", 45, 16),
]


def sections(company, language, role, service, days, hours):
    """Author-defined controls and qualifiers; generated before inspecting rankings."""
    if language == "en":
        policy = role == "policy"
        lead = "The supplier must" if policy else f"{company} confirms that its operators"
        statements = [
            (
                "Privileged access",
                "Which accounts require multiple authentication factors?",
                f"{lead} use multi-factor authentication when administering the {service} service.",
                "This requirement excludes non-interactive service identities, which instead need scoped credentials and rotation.",
                "The access owner maintains separate registers for people and automation. A person can approve a deployment without receiving standing access to the production database. Requests identify the tenant and the operational task. A quarterly review checks active assignments against those requests. Reviewers must distinguish a technical identity used by a scheduled job from a person signing in to the administrative console. Removing an employee must revoke their access even if the next scheduled review has not yet occurred.",
            ),
            (
                "Deletion and preservation",
                "When are customer records deleted and what is exempt?",
                f"Customer records {'must be' if policy else 'are'} removed within {days} calendar days of contract termination.",
                "The stated deadline excludes records under a documented litigation hold; those remain isolated until release is authorized.",
                "The customer contact authenticates the removal instruction and names the affected tenant. Operations first disables ordinary use, then tracks removal through the stores listed in the service inventory. A completion receipt records the scope and date. The receiving team checks any requested export before deletion proceeds. A downloadable file alone does not prove a successful handover. Requests concerning invoices follow a separate corporate records schedule and must not be confused with the customer-service data covered here.",
            ),
            (
                "Incident communication",
                "What starts the incident notification deadline?",
                f"The first customer incident notice {'must be' if policy else 'is'} sent within {hours} hours of awareness.",
                "The clock starts with a credible indication affecting customer data, not completion of the root-cause investigation.",
                "An on-call coordinator reviews alerts from operators, customers and infrastructure dependencies. The record distinguishes an observation from an unconfirmed hypothesis. Initial communication identifies the affected service, known impact and the next update route. Facts can change while containment continues. Corrections are added to the incident timeline rather than deleting an earlier entry. A tabletop exercise uses synthetic records to rehearse escalation. Completing that exercise does not prove that a real incident occurred or that every future incident will be resolved within the same time.",
            ),
            (
                "Storage protection",
                "Which stored data and temporary copies require encryption?",
                "Encryption at rest covers the primary store, replicas and recovery copies containing customer data.",
                "Temporary diagnostic exports containing customer records are also in scope, even when they are deleted after troubleshooting.",
                "The component register maps storage classes to accountable owners. A managed key service controls access to key material through a separate role. Support staff can request a redacted configuration sample, but the public assurance pack must not contain key identifiers or recovery secrets. The storage baseline covers data while stored; transport protection is reviewed independently. A screenshot showing an enabled setting is a declaration about that configuration, and an assessor may need a broader sample before relying on it across every component.",
            ),
            (
                "Location and remote support",
                "Where is production processing and can overseas support access records?",
                "Primary application processing and storage are located in the European Union.",
                "Specialist support in Canada may access the minimum necessary records under a separately approved task; the primary location statement does not exclude that access.",
                "The architecture diagram distinguishes routine computation, disaster recovery and operational support. Corporate office addresses are not used as a substitute for component locations. The supplier register identifies each provider's function and actual access category. Privacy reviewers examine the access route and contractual safeguards together. A provider incorporated abroad need not operate the production database there. Conversely, a database hosted in the agreed region does not establish that every support session originates from that region.",
            ),
            (
                "Assurance scope",
                "Does the independent audit cover the acquired support portal?",
                "The independent assurance report covers the established production platform for the current review year.",
                "It excludes the recently acquired support portal; an extension review is planned but has not been completed.",
                "The assurance register records the assessor, covered service, period and known exclusions. A company-wide certificate cannot replace the report's stated boundary. The owner can provide an authorized reviewer copy through the assurance contact. Commercial details may be redacted while retaining the scope statement. Management tracks outstanding actions separately from completed controls. An internal operating procedure is useful supporting material, but its existence does not turn an uncovered component into independently assessed infrastructure.",
            ),
        ]
        intro = (
            f"Synthetic {company} {role} document for {service}. No real organization or customer data. "
            "Coverage: production service, 2026-Q3. Rules and qualifications must be read together. "
            "The business owner records relationship purpose, data categories and access before assessment. "
            "A previous version may describe another service and must not silently replace this version."
        )
    else:
        policy = role == "policy"
        statements = [
            (
                "Dostęp uprzywilejowany",
                "Które konta wymagają uwierzytelniania wieloskładnikowego?",
                f"Administratorzy usługi {service} {'muszą używać' if policy else 'używają'} uwierzytelniania wieloskładnikowego.",
                "Ten obowiązek nie obejmuje nieinteraktywnych kont technicznych; dla nich wymagane są ograniczone uprawnienia i rotacja poświadczeń.",
                "Właściciel dostępu prowadzi oddzielny rejestr pracowników i automatyzacji. Zgłoszenie wskazuje klienta oraz zadanie operacyjne. Zatwierdzenie wdrożenia nie oznacza stałego dostępu do bazy produkcyjnej. Przegląd kwartalny porównuje aktywne uprawnienia z zatwierdzonymi rolami. Konto uruchamiające zadanie cykliczne ma inne zastosowanie niż konto człowieka w panelu administracyjnym. Odejście pracownika uruchamia odebranie dostępu bez oczekiwania na kolejny przegląd.",
            ),
            (
                "Usuwanie i zabezpieczenie danych",
                "Jaki jest termin usunięcia danych i kiedy obowiązuje wyjątek?",
                f"Dane klienta {'należy usunąć' if policy else 'są usuwane'} w ciągu {days} dni kalendarzowych od zakończenia umowy.",
                "Wyjątek stanowią wskazane dokumenty objęte obowiązkiem zabezpieczenia dowodów; pozostają odizolowane do zatwierdzenia zwolnienia blokady.",
                "Osoba kontaktowa uwierzytelnia dyspozycję i wskazuje właściwego klienta. Operator blokuje zwykłe wykorzystanie informacji, a następnie śledzi wykonanie czynności w magazynach z rejestru usługi. Potwierdzenie zawiera zakres oraz datę. Odbiorca sprawdza wymagany eksport przed zakończeniem przekazania. Sama możliwość pobrania pliku nie dowodzi jego przydatności. Faktury mają osobny harmonogram przechowywania i nie mogą być mylone z danymi usługi opisanej w tym dokumencie.",
            ),
            (
                "Zgłoszenie incydentu",
                "Od jakiego zdarzenia biegnie termin pierwszego powiadomienia?",
                f"Pierwsze powiadomienie klienta {'musi nastąpić' if policy else 'następuje'} w ciągu {hours} godzin od uzyskania świadomości incydentu.",
                "Początkiem terminu jest wiarygodny sygnał dotyczący danych klienta, a nie zakończenie ustalania przyczyny źródłowej.",
                "Dyżurny przyjmuje zgłoszenia od operatorów, klientów i dostawców infrastruktury. W zapisie rozróżnia obserwację od niepotwierdzonej hipotezy. Pierwszy komunikat wskazuje usługę, znany wpływ i kanał aktualizacji. Informacje mogą się zmienić podczas ograniczania skutków. Sprostowanie zostaje dodane do osi czasu zamiast usuwać wcześniejszy wpis. Ćwiczenie wykorzystuje dane syntetyczne. Jego przeprowadzenie nie oznacza, że wystąpił rzeczywisty incydent ani że każdy kolejny przypadek zostanie rozwiązany w identycznym czasie.",
            ),
            (
                "Ochrona magazynów",
                "Czy szyfrowanie obejmuje kopie i tymczasowe eksporty diagnostyczne?",
                "Szyfrowanie danych w spoczynku obejmuje magazyn główny, repliki i kopie odtworzeniowe zawierające dane klienta.",
                "Tymczasowe eksporty diagnostyczne z rekordami klientów także podlegają temu obowiązkowi, nawet jeżeli są usuwane po zakończeniu naprawy.",
                "Rejestr komponentów przypisuje właściciela każdej klasie magazynu. Usługa zarządzania kluczami ma osobne role administracyjne. Zespół wsparcia może udostępnić zanonimizowany przykład konfiguracji, ale pakiet oceny nie zawiera sekretów ani materiału odtworzeniowego. Ochronę transmisji ocenia się oddzielnie od przechowywania. Zrzut ekranu ustawienia opisuje konkretną konfigurację. Audytor może potrzebować szerszej próby, zanim odniesie taki dowód do wszystkich komponentów.",
            ),
            (
                "Lokalizacja i wsparcie",
                "Gdzie działają systemy i czy wsparcie spoza regionu ma dostęp do danych?",
                "Główne przetwarzanie i przechowywanie danych usługi odbywa się w Unii Europejskiej.",
                "Wsparcie specjalistyczne z Kanady może odczytać niezbędne rekordy w ramach odrębnie zatwierdzonego zadania; deklaracja głównej lokalizacji nie wyklucza tego dostępu.",
                "Diagram rozróżnia zwykłe przetwarzanie, odtwarzanie po awarii oraz obsługę operacyjną. Adres biura nie zastępuje lokalizacji komponentu. Rejestr dostawców opisuje funkcję i faktyczny zakres uprawnień. Osoba oceniająca prywatność sprawdza ścieżkę dostępu razem z zabezpieczeniami umownymi. Zagraniczna siedziba dostawcy nie dowodzi przeniesienia bazy do tego kraju. Baza w uzgodnionym regionie również nie dowodzi, że wszystkie sesje wsparcia pochodzą z tego regionu.",
            ),
            (
                "Zakres audytu",
                "Czy niezależny audyt obejmuje nowo przejęty portal wsparcia?",
                "Raport niezależnego audytora obejmuje dotychczasową platformę produkcyjną w bieżącym roku przeglądu.",
                "Nowo przejęty portal wsparcia jest wyłączony z tego zakresu; rozszerzenie przeglądu zaplanowano, ale nie zostało jeszcze zakończone.",
                "Rejestr dowodów wskazuje audytora, usługę, okres i wyłączenia. Certyfikat dotyczący spółki nie zastępuje określonych granic badania. Uprawniony recenzent może otrzymać kopię przez osobę kontaktową. Redakcja warunków handlowych pozostawia widoczny zakres oceny. Kierownictwo śledzi otwarte zadania oddzielnie od zakończonych kontroli. Wewnętrzna instrukcja jest materiałem pomocniczym, ale nie oznacza niezależnego zbadania komponentu, którego raport nie obejmuje.",
            ),
        ]
        intro = (
            f"Syntetyczny dokument {role} organizacji {company}. Usługa: {service}. "
            "Zakres: usługa produkcyjna, trzeci kwartał 2026. Nie zawiera danych rzeczywistych klientów. "
            "Zasady należy czytać razem z zastrzeżeniami. Właściciel biznesowy opisuje cel współpracy, "
            "rodzaje danych i uprawnienia. Wcześniejsza wersja może dotyczyć innej usługi."
        )
    return intro, statements


def render(intro, blocks, layout):
    parts = [intro]
    for heading, _, rule, qualifier, explanation in blocks:
        # Separation by a meaningful explanatory paragraph tests retained context.
        if layout == "markdown":
            parts.append(f"## {heading}\n\n{rule}\n\n{explanation}\n\n{qualifier}")
        elif layout == "mixed":
            parts.append(
                f"{heading}\n\n- {rule}\n\n{explanation}\n\n| Qualification |\n|---|\n| {qualifier} |"
            )
        else:
            parts.append(f"{rule} {explanation} {qualifier}")
    value = "\n\n".join(parts)
    if layout == "prose":
        value = value.replace("\n", " ")
    elif layout in {"wrapped", "pdf"}:
        value = "\n".join(textwrap.fill(part, width=74) for part in parts)
    return value + "\n"


def text_pdf(value):
    """Real text PDF with explicit page boundaries; Latin-1 English fixtures only."""
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    lines = value.splitlines()
    for start in range(0, len(lines), 45):
        page = writer.add_blank_page(612, 792)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        commands = ["BT /F1 10 Tf 12 TL 45 745 Td"]
        for line in lines[start : start + 45]:
            line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({line}) Tj T*")
        commands.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def freeze(directory):
    directory.mkdir(parents=True, exist_ok=True)
    assert not list(directory.iterdir()), "Use an empty directory to preserve frozen fixtures"
    corpus = []
    for company, language, split, service, days, hours in ORGANIZATIONS:
        for role in ("policy", "evidence"):
            intro, blocks = sections(company, language, role, service, days, hours)
            for layout in (
                "markdown",
                "prose",
                "wrapped",
                "mixed",
                *(("pdf",) if language == "en" else ()),
            ):
                suffix = (
                    ".pdf"
                    if layout == "pdf"
                    else ".md"
                    if layout in {"markdown", "mixed"}
                    else ".txt"
                )
                name = f"{company.lower()}-{role}-{layout}{suffix}"
                value = render(intro, blocks, layout)
                raw = text_pdf(value) if layout == "pdf" else value.encode()
                (directory / name).write_bytes(raw)
                corpus.append(
                    {
                        "file": name,
                        "organization": company,
                        "language": language,
                        "split": split,
                        "role": role,
                        "layout": layout,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "queries": [
                            {"id": str(i), "query": block[1], "anchors": [block[2], block[3]]}
                            for i, block in enumerate(blocks)
                        ],
                    }
                )
    (directory / "manifest.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"Frozen {len(corpus)} rendered documents / {sum(len(c['queries']) for c in corpus)} paired queries"
    )


def sentence_spans(text):
    boundaries = [0, *(m.end() for m in re.finditer(r"(?<=[.!?])\s+", text)), len(text)]
    return [
        (i, min(i + CHUNK_CHARS, b))
        for a, b in pairwise(boundaries)
        for i in range(a, b, CHUNK_CHARS)
    ]


def semantic_spans(text, model):
    units = sentence_spans(text)
    if not units:
        return []
    vectors = np.asarray(model.embed([text[a:b] for a, b in units], "passage"))
    distances = 1 - (vectors[:-1] * vectors[1:]).sum(axis=1)
    threshold = max(0.12, float(np.percentile(distances, 85))) if len(distances) else 1
    spans, start, end = [], units[0][0], units[0][0]
    for index, (a, b) in enumerate(units):
        should_cut = index and end - start >= 400 and distances[index - 1] >= threshold
        if end > start and (should_cut or b - start > CHUNK_CHARS):
            spans.append((start, end))
            lookback = units[index - 1][0]
            start = lookback if lookback > start and b - lookback <= CHUNK_CHARS else a
        end = b
    if end > start:
        spans.append((start, end))
    return spans


def source_pages(path):
    if path.suffix == ".pdf":
        return [(p.extract_text(), {"page": i + 1}) for i, p in enumerate(PdfReader(path).pages)]
    return [(path.read_text(), {})]


def split_document(path, variant, model):
    chunks, text, base = [], "", 0
    pages = source_pages(path)
    for page, location in pages:
        if variant == "current":
            original, _ = extract(page.encode(), "page.txt")
            spans, cursor = [], 0
            for c in original:
                a = page.index(c["text"], cursor)
                spans.append((a, a + len(c["text"])))
                cursor = a + len(c["text"])
        elif variant == "structure":
            spans = list(structured_spans(page))
        else:
            spans = semantic_spans(page, model)
        cursor = 0
        for a, b in spans:
            assert 0 <= a < b <= len(page) and b - a <= CHUNK_CHARS
            assert not page[cursor:a].strip() if a > cursor else True
            cursor = max(cursor, b)
            if page[a:b].strip():
                chunks.append(
                    {
                        "text": page[a:b],
                        "start": base + a,
                        "end": base + b,
                        "location": {
                            **location,
                            "line_start": page.count("\n", 0, a) + 1,
                            "line_end": page.count("\n", 0, b - 1) + 1,
                        },
                    }
                )
        assert not page[cursor:].strip()
        text += page + "\n"
        base = len(text)
    return text, chunks


def anchor_span(text, quote):
    pattern = r"\s+".join(
        re.escape(word).replace(r"\-", r"-(?:[ \t]*\n[ \t]*)?") for word in quote.split()
    )
    matches = list(re.finditer(pattern, text))
    assert len(matches) == 1, (quote, len(matches))
    return matches[0].span()


def covered(text, chunks, target):
    a, b = target
    cursor = a
    for c in sorted(chunks, key=lambda c: c["start"]):
        start, end = c["start"], c["end"]
        if end <= cursor:
            continue
        if start > cursor and text[cursor : min(start, b)].strip():
            return False
        cursor = max(cursor, end)
        if cursor >= b:
            return True
    return False


def summarize(rows):
    fields = ("hit@3", "hit@8", "hit@4000", "rule_without_qualifier", "budget_chars", "top8_chars")
    return {"n": len(rows), **{field: statistics.mean(r[field] for r in rows) for field in fields}}


def measure(directory, cache, output):
    manifest_raw = (directory / "manifest.json").read_bytes()
    corpus = json.loads(manifest_raw)
    # Validate frozen evidence before model work, including PDF line wrapping.
    for doc in corpus:
        text = "\n".join(page for page, _ in source_pages(directory / doc["file"]))
        for query in doc["queries"]:
            for quote in query["anchors"]:
                anchor_span(text, quote)
    model = LocalEmbedder(cache)
    queries = {q["query"] for doc in corpus for q in doc["queries"]}
    query_texts = sorted(queries)
    query_vectors = dict(zip(query_texts, model.embed(query_texts, "query"), strict=True))
    result = {
        "fingerprint": FINGERPRINT,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "protocol_sha256": hashlib.sha256(
            (ROOT / "adaptive-chunking-protocol.md").read_bytes()
        ).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "variants": {},
    }
    for variant in ("current", "structure", "semantic"):
        records, documents = [], []
        for doc in corpus:
            path = directory / doc["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == doc["sha256"]
            start = time.monotonic()
            text, chunks = split_document(path, variant, model)
            values = np.asarray(model.embed([c["text"] for c in chunks], "passage"))
            documents.append(
                {
                    "file": doc["file"],
                    "chunks": len(chunks),
                    "source_chars": len(text),
                    "embedded_chars": sum(len(c["text"]) for c in chunks),
                    "seconds": time.monotonic() - start,
                }
            )
            for query in doc["queries"]:
                targets = [anchor_span(text, quote) for quote in query["anchors"]]
                scores = values @ query_vectors[query["query"]]
                order = sorted(
                    range(len(chunks)), key=lambda i: (-float(scores[i]), chunks[i]["start"])
                )
                ranked = [chunks[i] for i in order]
                selected, used = [], 0
                for c in ranked:
                    if used + len(c["text"]) <= 4000:
                        selected.append(c)
                        used += len(c["text"])
                found = [covered(text, selected, target) for target in targets]
                records.append(
                    {
                        **{
                            k: doc[k]
                            for k in ("file", "organization", "split", "language", "role", "layout")
                        },
                        "id": query["id"],
                        "query": query["query"],
                        "hit@3": all(covered(text, ranked[:3], t) for t in targets),
                        "hit@8": all(covered(text, ranked[:8], t) for t in targets),
                        "hit@4000": all(found),
                        "rule_without_qualifier": found[0] and not found[1],
                        "budget_chars": used,
                        "top8_chars": sum(len(c["text"]) for c in ranked[:8]),
                        "ranking": [chunks[i]["location"] for i in order],
                    }
                )
        groups = {}
        for field in ("split", "language", "role", "layout", "organization"):
            for value in sorted({r[field] for r in records}):
                groups[f"{field}/{value}"] = summarize([r for r in records if r[field] == value])
        confirmation = [r for r in records if r["split"] == "confirmation"]
        for field in ("language", "role"):
            for value in sorted({r[field] for r in confirmation}):
                groups[f"confirmation/{field}/{value}"] = summarize(
                    [r for r in confirmation if r[field] == value]
                )
        result["variants"][variant] = {
            "all": summarize(records),
            "groups": groups,
            "documents": documents,
            "rows": records,
        }
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            variant,
            json.dumps({k: groups[k] for k in ("split/development", "split/confirmation")}),
            flush=True,
        )
    baseline = result["variants"]["current"]
    selected = max(
        ("structure", "semantic"),
        key=lambda name: result["variants"][name]["groups"]["split/development"]["hit@4000"],
    )
    candidate = result["variants"][selected]
    failures = []
    for split in ("development", "confirmation"):
        if (
            candidate["groups"][f"split/{split}"]["hit@4000"]
            - baseline["groups"][f"split/{split}"]["hit@4000"]
            < 0.05 - 1e-9
        ):
            failures.append(f"Less than 5 percentage points gain on {split}")
    for key in candidate["groups"]:
        if (
            key.startswith("confirmation/")
            and candidate["groups"][key]["hit@4000"] < baseline["groups"][key]["hit@4000"]
        ):
            failures.append(f"Regression in {key}")
    if (
        candidate["groups"]["split/confirmation"]["rule_without_qualifier"]
        > baseline["groups"]["split/confirmation"]["rule_without_qualifier"]
    ):
        failures.append("More rule-without-qualifier results")
    if candidate["all"]["top8_chars"] > 2 * baseline["all"]["top8_chars"]:
        failures.append("Context exceeds 2x baseline")
    if sum(d["seconds"] for d in candidate["documents"]) > 5 * sum(
        d["seconds"] for d in baseline["documents"]
    ):
        failures.append("Preparation exceeds 5x baseline")
    result["selection"] = {
        "candidate": selected,
        "preliminary_pass": not failures,
        "failures": failures,
        "atlas_regression_check": "Required only if preliminary gates pass",
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["selection"]), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("freeze", "measure"))
    parser.add_argument("--corpus", required=True, type=Path)
    parser.add_argument("--cache", default="/app/model-cache")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "freeze":
        freeze(args.corpus)
    else:
        assert args.output is not None
        measure(args.corpus, args.cache, args.output)


if __name__ == "__main__":
    main()
