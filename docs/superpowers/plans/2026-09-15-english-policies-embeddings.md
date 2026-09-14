# English workspace, substantial policies, local semantic retrieval

## Global constraints

Preserve tenant/case isolation, immutable analysis provenance, explicit human approvals, durable recovery and ticket idempotency. Application text is English; original source quotations retain their language. No credentials or private working files in Git. No paid fallback or publication. Use the existing feature branch. Back up database and original files before replacing the active synthetic dataset. Routine tests must not call paid providers.

## Task 1: English application

Translate all frontend screens, accessibility labels, metadata, dates and application-generated backend messages, reports, questions and ticket previews into natural English. Require English generated titles/explanations in model prompts without translating source quotes or changing structured API identifiers. Update existing browser checks and relevant backend expectations. Inspect all application files for leftovers. Preserve behavior. Verify frontend build and browser suite, backend tests and lint. Commit this stage separately.

## Task 2: Substantial synthetic policies and clean workspace

Create coherent substantial English policies for synthetic Northstar Labs: information security, privacy, supplier governance and incident response, with owners, versions, applicability, responsibilities, evidence expectations and exceptions. Provide grounded curated requirements with citations and meaningful synthetic long counterparty evidence for tests. Fresh bootstrap seeds only the new policy workspace and accounts, no old demo cases. Preserve old tiny fixtures solely for regression tests where needed. Back up running database and original document volume, verify backup usability, then replace active synthetic data with the clean seed. Verify custom policy extraction on large documents, limits, applicability and citations; implement bounded batching if necessary. Verify seed idempotency and clean user journey. Commit separately.

## Task 3: Local pretrained multilingual embeddings

Evaluate multilingual-e5-small CPU with fixed model revision and matching query/passage preprocessing. Automatically download public weights into a persistent worker model cache. API must not load the model. Worker indexes documents with visible pending/ready/error state and performs semantic query work; preserve immutable run snapshots and tenant filters. Adapt vector schema and version metadata, support reindexing, reject incompatible vectors. Keep worker recovery and bounded execution. Verify meaningful retrieval tests, fresh model download, cache reuse after restart, resource/latency measurements and lexical/semantic comparison. Document setup and limitations. Commit separately.

## Task 4: Ponytail whole-project audit and simplification

Use installed Ponytail audit and code-simplification guidance. Inspect entire project, simplify demonstrated unnecessary duplication/complexity, preserving required security, durability and functionality. Review changes independently. Run appropriate backend, evaluation, frontend and end-to-end checks against final stack. Commit simplifications separately and document actual verified outcomes, remaining limitations and required configuration.
