"""DEC commands (spec §5.2), one file per aggregate part.

Owned by track S (store, import, shadow); increments I2 and I3, spec §12.3, §12.4. Every command
reads before its unit of work (AP-4), calls the mirror guard, runs as one unit
(``kernel.store.api``) with versions, events and the idempotency key, and returns ``CommandResult``.
The signatures are the targets of ``dec.api``.
"""
