"""A fake ``EvidenceResolver``: evidence by ref, with the shared quote rule.

AT-N10 plants a journal-class item: ``FakeEvidenceResolver(items={'seg-1': Evidence(kind='segment',
ref='seg-1', occurred_at=None, data_class='journal', text='...')})``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coflow.kernel.ports.evidence_resolver import Evidence, quote_in_text


@dataclass
class FakeEvidenceResolver:
    kinds: frozenset[str] = frozenset({"segment", "message", "session", "document"})
    items: dict[str, Evidence] = field(default_factory=dict)
    calls: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)

    def resolve(self, ref: str) -> Evidence | None:
        self.calls.append(("resolve", (ref,)))
        return self.items.get(ref)

    def quote_matches(self, ref: str, quote: str) -> bool:
        self.calls.append(("quote_matches", (ref, quote)))
        item = self.items.get(ref)
        return bool(item and item.text and quote_in_text(quote, item.text))
