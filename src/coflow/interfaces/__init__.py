"""Interfaces: the admin API and CLI (ADM), the MCP server (Streamable HTTP on loopback, a local
stdio shim) and the card views. Interfaces import only modules' ``api`` (and ``events``) and
orchestrate cards that span modules, each item in its owner's own unit of work (spec §4.3).

Owned by track X (interfaces); increment I1, spec §12.2.
"""
