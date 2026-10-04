# Building in public

CoFlow 2.0 is developed in the open, and the development itself is documented as a decision case: every
stage is a decision with grounds, a commitment with a date, actions, an outcome and a lesson — the same
chain the system keeps for its owner.

```
Signal → Decision → Commitment → Action → Outcome → Learning
```

## The rubric

- **Working name (proposed):** "Decision system at work" (English) / «Decision system в работе» (Russian).
- **Cadence:** one episode a week, whatever the stage boundaries.
- **Proposed: review** after the fourth episode or 30 days after the first one, whichever comes first
  (see "Review gate").

## Episode template

Every episode, whatever the channel, follows one skeleton:

| Part | Content |
|---|---|
| Signal | What prompted the work: a failure, a number, a need from real use |
| Decision | What was decided, the alternatives, why |
| Commitment | What was promised and by when (the stage and its exit criteria) |
| Action | What was built and how: agents, reviews, tests |
| Tested | What was tested and accepted: the per-module acceptance results from the module cards, drills run (deploy, rollback, restore) |
| Outcome | What happened against the commitment, including what did not work |
| Learning | The rule that comes out of it |
| Numbers | Agent tokens, model API cost, the author's hours, review findings, tests, defects after release |
| Artifacts | Tag, pull requests, a diagram or a short screen recording on synthetic data |

Numbers are measured. An estimate is marked as an estimate.

## Season 0 — "What v1 taught me" (published before and alongside stage 0)

| # | Episode | Source |
|---|---|---|
| 0.1 | Why CoFlow 2.0 is open source and not a product | [DECISIONS.md](DECISIONS.md) D-001, D-005 |
| 0.2 | Twenty web pages, one used: why the interfaces are a bot and MCP | [LESSONS_FROM_V1.md](LESSONS_FROM_V1.md) §1 |
| 0.3 | 1,785 suggestions, 10 decisions: why background queues die | §1 |
| 0.4 | Where does a message go? Routing between work and the private journal | §4 |
| 0.5 | 233k rows under one lock: SQLite with nine writers | §2 |
| 0.6 | Where $54.78 went, and why the prompt prefix sets the price | §7 |
| 0.7 | Agents reviewing agents: when to stop polishing | §8 |
| 0.8 | The system that always agreed with me: why an alignment check must be able to say "can't judge" | §7; [DECISIONS.md](DECISIONS.md) D-017 |
| 0.9 | ∫G = V × E: what can be measured between people, and what must be pre-registered | [REQUIREMENTS.md](REQUIREMENTS.md) §5.20 |
| 0.10 | Microservices or a modular monolith? Why one writer wins for a personal system | [DECISIONS.md](DECISIONS.md) D-030 |

## Season 1 — the build (stages 0–7: the R1 release episode after stage 5, then the switch-over and the learning loop)

One episode every week: what was done, tested and worked through that week, including a stage of
[ROADMAP.md](ROADMAP.md) still in progress; a stage's acceptance results go into the episode of the week it
closes. After stage 5 comes the R1 release episode: what a new user can install, what it costs to run,
what is still missing. Running through the season:

- **From a laptop to a home server.** CI/CD and Docker for a personal system: the delivery skeleton
  (stage 0), the home host and remote administration (stage 2), signed releases, approvals and automatic
  rollback (stage 5), the move of real data (stage 6) — as a path others can repeat
  ([DEPLOYMENT.md](DEPLOYMENT.md)).
- **Module cards in practice.** How each module is specified, measured and accepted
  ([MODULES.md](MODULES.md)).

## Season 2 — modules after the switch-over

One episode every week: what was done, tested and worked through that week, including a stage-8 module
still in progress; a module's acceptance results go into the episode of the week it closes. Modules follow
the order of the roadmap. Recurring topics:

- **Finding the centre.** The author's own story of forming a manifest, a life vision and goals, and of
  returning to that centre — told by the author's choice, next to the goals module's protocols, its
  synthetic evaluation set and its aggregate usage signals.
- **A country pack per tax year.** What changed in the rules, how the golden tests caught it.

## Channels

| Channel | Language | Role |
|---|---|---|
| GitHub (`DEVLOG.md`, releases, discussions) | English | Canonical record; every episode links here |
| Telegram channel | Russian | Short episode with the main number and lesson |
| LinkedIn | English | Short episode for an international audience |
| Video (optional) | Russian / English | Studio recording for selected episodes |

## How an episode is made

1. During the week the author records observations as short voice or text notes.
2. At the end of the week an agent drafts the episode from the week's work, the stage report when a stage
   closed, the numbers and the notes.
3. The author edits the draft; nothing is published without the author's explicit approval.
4. A final check removes any personal or third-party data.
5. The Russian and English versions are published; the canonical text goes into `DEVLOG.md`.

## Rules

- **Synthetic data only.** No real conversations, names, contacts, chats or screenshots of the author's
  instance. Demo material comes from the synthetic fixture set.
- **People in the author's life are never content** without their explicit consent.
- **The author's own story is shared only by the author's choice.** Nothing from the author's journal,
  centre documents, money or tax figures appears in an episode unless the author selects it for that
  episode.
- **No identifiers of the author's infrastructure** — host names, addresses, domains, VPN or tunnel ids,
  SSH users, registry paths — in episodes or public CI output; deployment demos use a synthetic host.
- **Failures are published with the same weight as successes.**
- **No promises of dates to users.** The roadmap gives targets; episodes report facts.

## Review gate

Proposed: after the fourth episode or 30 days, the author decides to continue, change or stop the rubric
based on:

- qualified replies: people who want to try CoFlow, contribute, or discuss decision systems;
- issues and discussions opened by others;
- reported installations after R1;
- the author's time per episode.

Reach (views, likes) is recorded but does not decide on its own.
