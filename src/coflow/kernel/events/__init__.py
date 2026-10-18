"""EVT: events written in the same unit of work as the change, delivered after commit (ARCHITECTURE
§6.2, spec §4.6). Payloads carry ids, entity type and changed field names, never values (AT-K6).

Owned by track K (kernel); increment I1, spec §12.2: ``publish.py`` and ``dispatch.py``.
"""
