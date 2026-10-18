"""The ``coflow`` command line (spec §5.6): a thin client of the core's loopback admin API.

Owned by track X (interfaces); increment I1, spec §12.2. ``main`` runs every command (the
``[project.scripts]`` entry point ``coflow.app.supervisor:main`` calls it with the composition
root's launcher) and its signature is fixed by the skeleton; the track implements the commands of
I1:
``coflow init``, ``doctor``, ``run``, ``mcp-stdio``, ``mcp token new``, ``dec import v1``,
``dec waiting`` (with ``--brief`` and the documented morning-pull recipe), ``dec show``,
``dec list``, ``dec shadow``, ``dec integrity``.

The local CLI is an owner channel (``CommandContext(channel='cli', owner_channel=True)``). When the
core is not running it starts an ephemeral core in-process under the same instance lock, so there is
never a second writer (§4.5). It imports modules only through their ``api``.

Every command but ``mcp-stdio`` works on one instance: its data root comes from ``--data-root`` or
the ``COFLOW_DATA_ROOT`` environment variable. ``--json`` prints the view itself (the same data MCP
returns) instead of text. Exit codes: 0 done, 1 refused or a failed check, 2 a usage error.

Spec note: the composition root (``coflow.app``) sits above the interfaces in the ``top`` import
contract, so this module may not import it. ``main`` therefore takes the ``CoreLauncher`` as a
keyword argument (tests pass fakes). The ``coflow`` entry point is ``coflow.app.supervisor:main``,
which passes the launcher explicitly (integration: the skeleton change track X reported); a direct
call of this ``main`` without a launcher still late-binds the composition root by its module name
(``_COMPOSITION_ROOT``).

Further spec notes: ``init`` without ``--timezone`` uses UTC and says so (§5.6 shows the option as
optional and names no default; the host's zone is never used). ``dec waiting --drafts`` is left to
I2, where drafts first exist. ``dec waiting --recipe`` prints the documented morning-pull recipe,
which is also the epilog of ``coflow dec waiting --help``.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import os
import sys
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TextIO, cast
from zoneinfo import ZoneInfoNotFoundError

from coflow.interfaces.admin import render
from coflow.interfaces.admin.api import (
    AdminClient,
    AdminFailure,
    AdminService,
    CoreLauncher,
    HttpAdminClient,
    LocalAdminClient,
    read_endpoint,
    remove_endpoint,
)
from coflow.interfaces.mcp.stdio_shim import DEFAULT_PORT, DEFAULT_URL, TOKEN_ENV, URL_ENV, run_shim
from coflow.interfaces.views.card import Wire, error_view
from coflow.kernel.context import SystemClock, new_salt, parse_instant, zone
from coflow.kernel.errors import CoflowError
from coflow.kernel.ops.doctor import run_doctor
from coflow.kernel.ops.init import init_instance

__all__ = ["DATA_ROOT_ENV", "build_parser", "main"]

DATA_ROOT_ENV = "COFLOW_DATA_ROOT"
_COMPOSITION_ROOT = "coflow.app.supervisor"

OK, REFUSED, USAGE = 0, 1, 2


class _UsageError(Exception):
    pass


# ==================================================================================================
# The parser


def _day(text: str) -> str:
    try:
        date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a date YYYY-MM-DD") from None
    return text


def _instant(text: str) -> str:
    try:
        parse_instant(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not an instant such as 2026-11-01T12:00Z"
        ) from None
    return text


def _run_id(text: str) -> str:
    if text == "latest" or (text.isdigit() and int(text) > 0):
        return text
    raise argparse.ArgumentTypeError("--run takes 'latest' or a run number")


def _common() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--data-root",
        default=argparse.SUPPRESS,
        metavar="PATH",
        help=f"the instance's data root (default: ${DATA_ROOT_ENV})",
    )
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="print the view as JSON (the data MCP returns) instead of text",
    )
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common()
    parser = argparse.ArgumentParser(
        prog="coflow",
        description="CoFlow 2.0: a self-hosted personal decision system.",
    )
    parser.add_argument("--data-root", default=None, metavar="PATH", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", default=False, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("init", parents=[common], help="create an instance in a data root")
    p.add_argument("--role", required=True, choices=["dev", "validation"])
    p.add_argument("--timezone", default=None, metavar="ZONE", help="the owner's IANA zone")
    p.add_argument("--issuer", default="CF", metavar="CODE", help="the instance's issuer code")

    sub.add_parser(
        "doctor",
        parents=[common],
        help="check the role, the lock, the data root and the schema revision",
    )

    p = sub.add_parser("run", parents=[common], help="serve MCP and the admin API on loopback")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"(default {DEFAULT_PORT})")

    p = sub.add_parser(
        "mcp-stdio", help="the stdio shim for local AI clients (forwards to the running core)"
    )
    p.add_argument(
        "--url", default=None, help=f"the core's MCP endpoint (default ${URL_ENV} or {DEFAULT_URL})"
    )
    p.add_argument(
        "--token-file",
        default=None,
        metavar="PATH",
        help=f"a file holding the client token (default ${TOKEN_ENV})",
    )

    mcp = sub.add_parser("mcp", help="MCP client tokens").add_subparsers(
        dest="mcp_command", required=True, metavar="COMMAND"
    )
    token = mcp.add_parser("token", help="client tokens").add_subparsers(
        dest="token_command", required=True, metavar="COMMAND"
    )
    p = token.add_parser("new", parents=[common], help="issue a token for an MCP client")
    p.add_argument("--client", required=True, metavar="NAME")
    p.add_argument("--scope", required=True, choices=["read", "write"])
    p.add_argument("--financial", action="store_true", help="let the client see money amounts")

    dec = sub.add_parser("dec", help="decisions").add_subparsers(
        dest="dec_command", required=True, metavar="COMMAND"
    )
    imp = dec.add_parser("import", help="import a snapshot").add_subparsers(
        dest="import_format", required=True, metavar="FORMAT"
    )
    p = imp.add_parser(
        "v1",
        parents=[common],
        help="a coflow.import.decisions v1 snapshot (validation role; dev: synthetic files only)",
    )
    p.add_argument("snapshot", metavar="SNAPSHOT.json")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--final", dest="mode", action="store_const", const="final")
    mode.add_argument("--dry-run", dest="mode", action="store_const", const="dry_run")

    p = dec.add_parser("shadow", parents=[common], help="the shadow report of a snapshot run")
    p.add_argument("--run", type=_run_id, default="latest", help="latest (default) or N")

    p = dec.add_parser(
        "waiting",
        parents=[common],
        help="what is waiting and why",
        epilog=render.render_recipe(None),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--date", type=_day, default=None, help="evaluate on this day (YYYY-MM-DD)")
    p.add_argument("--brief", action="store_true", help="at most 8 items, one line each")
    p.add_argument("--recipe", action="store_true", help="print the morning-pull recipe")

    p = dec.add_parser("show", parents=[common], help="the card of one decision")
    p.add_argument("ref", metavar="REF")
    p.add_argument("--full", action="store_true")
    p.add_argument("--as-of", type=_instant, default=None, metavar="INSTANT")
    p.add_argument("--axis", choices=["knowledge", "instance", "occurrence"], default="knowledge")

    p = dec.add_parser("list", parents=[common], help="one line per decision")
    p.add_argument("--status", default=None)
    p.add_argument("--health", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--mirror", default=None, metavar="ISSUER")
    p.add_argument("--linked-to", default=None, metavar="REF")
    p.add_argument("--limit", type=int, default=50)

    p = dec.add_parser("integrity", parents=[common], help="check the sealed editions")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("ref", nargs="?", metavar="REF")
    target.add_argument("--all", action="store_true")
    return parser


# ==================================================================================================
# Running commands


def _default_launcher() -> CoreLauncher:
    module = importlib.import_module(_COMPOSITION_ROOT)
    return cast(CoreLauncher, module.LAUNCHER)


def _data_root(args: argparse.Namespace, environ: Mapping[str, str]) -> Path:
    raw = args.data_root or environ.get(DATA_ROOT_ENV)
    if not raw:
        raise _UsageError(f"no data root: pass --data-root PATH or set {DATA_ROOT_ENV}")
    return Path(raw).expanduser().resolve()


def _interaction_id() -> str:
    return "cli-" + new_salt()[:16]


@contextmanager
def _admin(data_root: Path, launcher: CoreLauncher) -> Iterator[AdminClient]:
    """The running core's admin API, else an ephemeral core under the instance lock."""
    interaction_id = _interaction_id()
    endpoint = read_endpoint(data_root)
    if endpoint is not None:
        try:
            client = HttpAdminClient(endpoint, interaction_id=interaction_id)
        except ValueError as exc:
            raise _UsageError(f"refusing the endpoint file of {data_root}: {exc}") from None
        try:
            client.call("ping", {})
        except OSError:
            pass  # a stale endpoint file: the core is gone, the lock is free again
        else:
            yield client
            return
    with launcher.open(data_root) as services:
        if endpoint is not None:
            # This process now holds the instance lock, so no core runs: the file is stale.
            remove_endpoint(data_root)
        yield LocalAdminClient(AdminService(services), interaction_id=interaction_id)


def _operation(args: argparse.Namespace) -> tuple[str, dict[str, object]]:
    if args.command == "mcp":
        return "mcp.token.new", {
            "client": args.client,
            "scope": args.scope,
            "financial": bool(args.financial),
        }
    sub = args.dec_command
    if sub == "import":
        path = Path(args.snapshot).expanduser().resolve()
        if not path.is_file():
            raise _UsageError(f"no snapshot file at {path}")
        return "dec.import.v1", {"path": str(path), "mode": args.mode or "shadow"}
    if sub == "shadow":
        return "dec.shadow", {"run_id": None if args.run == "latest" else int(args.run)}
    if sub == "waiting":
        return "dec.waiting", {"date": args.date, "brief": bool(args.brief)}
    if sub == "show":
        return "dec.show", {
            "ref": args.ref,
            "full": bool(args.full),
            "as_of": args.as_of,
            "axis": args.axis,
        }
    if sub == "list":
        if args.limit < 1:
            raise _UsageError("--limit must be at least 1")
        return "dec.list", {
            "status": args.status,
            "health": args.health,
            "kind": args.kind,
            "mirror": args.mirror,
            "linked_to": args.linked_to,
            "limit": args.limit,
        }
    if sub == "integrity":
        return "dec.integrity", {"ref": "all" if args.all else args.ref}
    raise _UsageError(f"unknown command dec {sub}")  # pragma: no cover - argparse refuses first


def _print_view(view: Wire, *, as_json: bool, brief: bool, out: TextIO) -> None:
    if as_json:
        print(json.dumps(view, ensure_ascii=False, indent=2), file=out)
    else:
        print(render.render_view(view, brief=brief), file=out)


def _print_failure(
    payload: Mapping[str, object], *, as_json: bool, out: TextIO, err: TextIO
) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=out)
    else:
        print(render.render_error(payload), file=err)


def _cmd_init(args: argparse.Namespace, data_root: Path, out: TextIO) -> int:
    tz = args.timezone
    if tz is None:
        tz = "UTC"
        print("note: no --timezone given; the owner zone is UTC (every 'today' uses it)", file=out)
    try:
        zone(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise _UsageError(f"{tz!r} is not an IANA time zone such as Europe/Berlin") from None
    data_root.mkdir(parents=True, exist_ok=True)
    info = init_instance(
        data_root, role=args.role, clock=SystemClock(), timezone=tz, issuer=args.issuer
    )
    print(render.render_init(info, data_root, timezone=tz), file=out)
    return OK


def _cmd_doctor(data_root: Path, out: TextIO) -> int:
    report = run_doctor(data_root)
    print(render.render_doctor(report), file=out)
    return OK if report.ok else REFUSED


def _cmd_shim(args: argparse.Namespace, environ: Mapping[str, str], err: TextIO) -> int:
    url = args.url or environ.get(URL_ENV) or DEFAULT_URL
    if args.token_file:
        try:
            token = Path(args.token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise _UsageError(f"cannot read the token file: {exc}") from None
    else:
        token = environ.get(TOKEN_ENV, "").strip()
    return run_shim(url, token, stderr=err)


def _reconfigure(stream: TextIO) -> None:
    encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
    reconfigure = getattr(stream, "reconfigure", None)
    if encoding != "utf8" and reconfigure is not None:
        # A stream that cannot change its encoding keeps its own.
        with contextlib.suppress(ValueError, OSError):
            reconfigure(encoding="utf-8", errors="replace")


def main(
    argv: Sequence[str] | None = None,
    *,
    launcher: CoreLauncher | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run the CLI with ``argv`` (default ``sys.argv[1:]``) and return the process exit code."""
    env = os.environ if environ is None else environ
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse: --help (0) or a usage error (2)
        return int(exc.code or 0)
    out, err = sys.stdout, sys.stderr
    if args.command != "mcp-stdio":
        _reconfigure(out)
        _reconfigure(err)
    as_json = bool(getattr(args, "json", False))
    try:
        if args.command == "mcp-stdio":
            return _cmd_shim(args, env, err)  # never resolves a data root (AT-K7)
        if args.command == "dec" and args.dec_command == "waiting" and args.recipe:
            raw = args.data_root or env.get(DATA_ROOT_ENV)
            print(render.render_recipe(Path(raw) if raw else None), file=out)
            return OK
        data_root = _data_root(args, env)
        if args.command == "init":
            return _cmd_init(args, data_root, out)
        if args.command == "doctor":
            return _cmd_doctor(data_root, out)
        core = launcher or _default_launcher()
        if args.command == "run":
            return core.serve(data_root, port=args.port)
        op, op_args = _operation(args)
        brief = bool(getattr(args, "brief", False))
        with _admin(data_root, core) as admin:
            view = admin.call(op, op_args)
        _print_view(view, as_json=as_json, brief=brief, out=out)
        return OK
    except _UsageError as exc:
        print(f"coflow: {exc}", file=err)
        return USAGE
    except AdminFailure as failure:
        _print_failure(failure.payload, as_json=as_json, out=out, err=err)
        return REFUSED
    except CoflowError as error:
        _print_failure(error_view(error, instance_role=None), as_json=as_json, out=out, err=err)
        return REFUSED
