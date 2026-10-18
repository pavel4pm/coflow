"""STO: storage, numbered migrations, the table registry, generated triggers, the transaction log
and the instance lock (spec §2.1, §2.3).

The public contract is ``api.py`` (skeleton); everything else in this package is track K's.

Owned by track K (kernel); increment I1, spec §12.2.
"""
