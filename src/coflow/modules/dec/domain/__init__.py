"""DEC's pure domain: frozen views in ``model.py`` (skeleton) and pure functions over them. Nothing
here opens a connection, reads a clock or draws randomness: every computed function takes ``T``
(``EvalTime``) and the configuration (``DecConfig``) explicitly (spec §12.5).

Owned by track D (decision domain, pure functions); increment I1, spec §12.2: ``cfj``, ``dates``,
``due``, ``states``, ``health``, ``waiting``, ``context_card``, ``goals``.
"""
