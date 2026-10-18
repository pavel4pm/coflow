"""The composition root: binds the store, builds each module's environment with its port
implementations and registers handlers (ARCHITECTURE §5.1). It imports modules only through
their ``api``.

Owned by track X (interfaces); increment I1, spec §12.2.
"""
