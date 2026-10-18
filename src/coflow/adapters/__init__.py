"""Adapters: provider, messenger, calendar, file and invoice readers (ARCHITECTURE §5.1).

Wired only by ``coflow.app``; the kernel, modules and interfaces never import them
(``.importlinter`` contract ``adapters``). Empty in the slice, which is model-free and offline.
"""
