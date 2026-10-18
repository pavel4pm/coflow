"""Domain modules in tiers (ARCHITECTURE §5.1; ``.importlinter`` contract ``domain``).

In the slice: ``dec`` (tier 2), ``cmt`` (tier 3, minimal, I3) and ``aln`` (tier 8, an empty package
that keeps its place in the contract). A module imports only the ``api`` of modules in lower tiers;
from outside a module only its ``api`` (and ``events``) may be imported (``tests/architecture``).
"""
