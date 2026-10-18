"""IDS: the numbering tap, the prefix registry, foreign and burned numbers, aliases and tolerant
input (IDN-1, IDN-2, spec §2.2, §6.4).

Public functions other tracks call: ``registry.prefix_spec``, ``tap.issue``,
``tap.register_foreign``, ``tap.burn``, ``codes.render``, ``codes.render_scoped``,
``codes.parse``, ``codes.canonical``, ``aliases.add_alias``, ``aliases.resolve``.

Owned by track K (kernel); increment I1, spec §12.2: ``registry.py``, ``tap.py``, ``codes.py``,
``aliases.py``.
"""
