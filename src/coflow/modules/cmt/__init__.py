"""CMT: commitments (minimal in the slice), tier 3, increment I3 (spec §2.5, §5.4).

Who owes what to whom by when, by what success criterion, executing a decision or saying "no
decision" on purpose. CMT reaches decisions only through the ``DecisionDirectory`` port (never
``dec`` internals) and implements ``DecisionAttachmentProbe``. ``api.py`` and ``model.py`` are
skeleton files; ``commands.py``, ``queries.py``, ``probe.py`` and ``migrations/`` are track C's.
"""
