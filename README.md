# CoFlow

**An open-source personal decision system.** CoFlow runs on a computer you control — your desktop, a home
server or any Docker host — collects the signals you already have — conversations, recordings, messages,
your calendar — and keeps the chain from a signal to a decision, a commitment, an action, an outcome and
what you learned. You work with it through a Telegram bot and through AI clients (Claude and others) over
MCP. It proposes; you decide. Nothing changes the outside world without your explicit approval, and
everything that leaves the CoFlow host or travels between your devices and it — text for the model
provider, for example — is listed in one data-flow document, with a switch.

```
Signal → Decision → Commitment → Action → Outcome → Learning
```

> **Status: requirements stage (October 2026).** No code yet. CoFlow 2.0 is a clean rewrite of a private
> system (v1) its author has used daily since spring 2026. The requirements, the architecture, the
> deployment design, the plan and the lessons from v1 are in `docs/`. Development starts after the v1
> acceptance period ends (planned mid-October 2026) and happens in public, with a weekly episode on what
> was built and tested.

## What it is

- **Memory of people and conversations.** Who someone is, what you discussed, what each side promised —
  every fact with its source and a quote.
- **Decisions and commitments as first-class records.** A decision keeps its grounds and the assumptions to
  watch; a commitment knows who owes what to whom and by when.
- **Meetings end to end.** Plan, brief, record, outcome — the recording finds its meeting, the outcome turns
  into proposed commitments you confirm with one tap.
- **A daily and weekly rhythm.** A morning plan computed by an algorithm (not invented by a model), an
  evening "plan vs. fact", a weekly review.
- **A timeline of everything.** What happened on a given day or around an event, across every layer of
  your history.
- **Chat-first.** A Telegram bot for the phone, MCP for AI clients on your desktop — connected to CoFlow on
  the same machine or on your server. A web UI only where it is proven to be needed.
- **After the first release:** your centre and goals — formed in your own words and followed with
  computed, evidence-based checks; money per book (household, own practice, company) with a tax calendar
  and labelled estimates through country packs — CoFlow registers invoices from a certified invoicing program rather than issuing
  them, and files no returns (D-026). Deeper analysis — alignment,
  relationships, the *conductivity* of human interaction — is research built on the same data.

> CoFlow is not tax, legal or financial advice. Tax calendars and figures are planning estimates from
> versioned country packs that may be outdated or wrong; confirm anything you file or pay with a qualified
> advisor.

## What it is not

- Not a team tool, not a sales CRM, not a SaaS. One installation = one owner. It is a personal CRM-like
  registry of your people, tasks and commitments, with a control view of what is moving, what is stuck
  and how your actions compare with your plans.
- Not an autonomous agent. It never sends messages, creates events or adds people on its own; modules
  that write to other people are off by default and act only on your explicit instruction.
- Not cloud-first. Audio is transcribed on your CoFlow host. Text goes to the model provider you
  configure, as listed in the data-flow document. The private journal stays out of search, tools and work
  answers, and reaches a model only if you switch it on for an analysis module.

## How it runs

- **Production:** one Docker Compose stack — proposed: on a Linux host (D-020), a home server or a rented
  one — with exactly one writing instance. Releases are built and signed by CI on GitHub; the host pulls
  and verifies them itself, and you approve each deploy.
- **Development:** native Python on Windows or Linux, with fakes and synthetic data.
- **Your devices** reach the host through a private network (an overlay VPN plus SSH); nothing listens on a
  public interface by default.

## Principles in one screen

1. Self-hosted, one owner, one production instance.
2. The private journal is a separate data class: no index, no tools; a model only by your explicit switch.
3. The system proposes, the owner decides; external writes are idempotent and verified.
4. Rules — not models — decide where text goes.
5. Evidence over inference: sources, quotes, and an honest "can't judge".
6. Compute once, keep provenance, recompute only when the input changes.
7. Build only what real use proves; an unreviewed queue is a defect.
8. Modules with contracts and their own quality gates — inside one writing process (D-030).

## Documents

| Document | What is inside |
|---|---|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Product thesis, principles, functional and non-functional requirements, scope and non-goals |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The modular monolith: modules, contracts, data classes, process view |
| [docs/MODULES.md](docs/MODULES.md) | One card per module: owned data, contracts, quality parameters, acceptance |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Install paths, the production host, CI/CD, access, backups, drills |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Stages, exit criteria, estimates, switch-over from v1 |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log (why open source, why this architecture and deployment) |
| [docs/LESSONS_FROM_V1.md](docs/LESSONS_FROM_V1.md) | What the private v1 taught in its first months — incidents, numbers, fixes |
| [docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md) | How the development is documented in public |
| [DEVLOG.md](DEVLOG.md) | The development log: one entry per episode, with the numbers behind it |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to take part at this stage |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability; what CoFlow protects |

## Disclaimer

CoFlow is not tax, legal or financial advice. Tax calendars and figures are planning estimates from
versioned country packs that may be outdated or wrong; confirm anything you file or pay with a qualified
advisor.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
