"""Ports: protocols that let a lower tier use something a higher tier owns (ARCHITECTURE §5.1).

Skeleton package (spec §12.1, §4.2). Each port module holds the protocol and its DTO dataclasses;
each has a fake in ``tests/fakes/``. The composition root (``coflow.app``) registers the
implementations.

- ``DecisionDirectory``: implemented by DEC (``modules/dec/directory.py``); used by CMT, later by
  SIG, PPL, CAL, WRK, MTG and RHY.
- ``DecisionAttachmentProbe``: implemented by CMT (I3); used by DEC (review card, history, metrics).
- ``EvidenceResolver``: built-ins (I2), SIG at stage 1; used by DEC (facts, checks, readings).
- ``GoalDirectory``: DEC's shadow adapter over mirrored goal context (I1), WRK at stage 1; used by
  DEC.
- ``UndoHandler``: every module with MCP write tools (I2); used by the undo command, ACT from
  stage 2.

Ports return ids, counts, change names and short titles only: never another module's text or data.
"""
