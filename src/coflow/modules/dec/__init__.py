"""DEC: decisions, the aggregate root of CoFlow 2.0 (spec §1-§6).

Tier 2: DEC imports nothing above tier 2. It reads spokes through ``DecisionAttachmentProbe``,
validates evidence through ``EvidenceResolver`` and reads goals through ``GoalDirectory``; spokes
and same-tier modules reach it through ``DecisionDirectory``. The public surface is ``api.py``.

File ownership (spec §12.2): ``api.py``, ``domain/model.py`` and ``domain/inputs.py`` are skeleton
files; ``domain/*`` and ``queries.py`` are track D's; ``migrations/``, ``store/``, ``importer/``,
``shadow/`` and ``goals_shadow.py`` are track S's; ``directory.py``'s read side is I1 (integration)
and its attachment checks and entry offers are track C's (I3).
"""
