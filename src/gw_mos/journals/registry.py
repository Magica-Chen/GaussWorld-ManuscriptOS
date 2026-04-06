from __future__ import annotations

from gw_mos.journals.base import JournalProfile


JOURNAL_PROFILES = {
    "elsevier": JournalProfile(
        family="elsevier",
        scope_summary="Elsevier family profile scaffold.",
        template_hint="Prefer local elsarticle assets.",
    ),
    "springer_nature": JournalProfile(
        family="springer_nature",
        scope_summary="Springer Nature family profile scaffold.",
        template_hint="Prefer local sn-article-template assets.",
    ),
    "custom": JournalProfile(
        family="custom",
        scope_summary="User-provided template adapter scaffold.",
        template_hint="Use explicit template path metadata.",
    ),
}


def get_journal_profile(name: str) -> JournalProfile:
    return JOURNAL_PROFILES.get(name, JOURNAL_PROFILES["custom"])
