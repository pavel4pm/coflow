"""CoFlow 2.0 test suite: synthetic, offline, temp data roots, a fake clock and fake ports.

Layout (file ownership follows spec §12.2): ``tests/kernel/`` (track K), ``tests/modules/dec/``
(tracks D and S, by file), ``tests/oracle/`` (track S), ``tests/interfaces/`` (track X),
``tests/architecture/`` and ``tests/test_smoke.py`` (skeleton), ``tests/fakes/`` and
``tests/fixtures/synthetic/`` (shared, append only).
"""
