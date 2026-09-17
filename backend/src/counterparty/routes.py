"""Register the organization-scoped API domains."""

from fastapi import APIRouter

from counterparty.api import analyses, audit, auth, cases, documents, policies

router = APIRouter(prefix="/api")
for domain in (auth, cases, documents, policies, analyses, audit):
    router.include_router(domain.router)
