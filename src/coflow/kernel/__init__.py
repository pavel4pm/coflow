"""The kernel: storage, identity, events, policy, configuration, operations and observability.

Layers inside the kernel (``.importlinter``, contract ``kernel``), top to bottom::

    ops > obs > models | actions > policy > events > ids | config > store | ports > context | errors

``models`` and ``actions`` arrive in stage 0B and stage 2. Owned by track K, except the skeleton
files ``context.py``, ``errors.py``, ``ports/`` and ``store/api.py``, which change only through a
reviewed skeleton pull request (spec §12.5).
"""
