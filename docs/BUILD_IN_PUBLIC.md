# Building in public

CoFlow 2.0 is developed in the open, and the development itself is documented as a decision case: every
stage is a decision with grounds, a commitment with a date, actions, an outcome and a lesson — the same
chain the system keeps for its owner.

```
Signal → Decision → Commitment → Action → Outcome → Learning
```

## The rubric

- **Working name (proposed):** "Decision system at work" (English) / «Decision system в работе» (Russian).
- **Format (accepted by the author, 4 October 2026): the machine drives, the author decides.** Coding
  agents follow the roadmap week by week — they build, test, release and draft the episodes; the author
  tests, tells what it was like to use, makes the decisions and publishes.
- **Cadence:** a main episode every Monday (video and posts) and a short lesson post on Thursdays — at
  most two touches a week.
- **Review:** on 9 November 2026, after the fourth main episode (see "Review gate").

## The weekly cycle

| When | The machine | The author |
|---|---|---|
| Monday | Starts the week's work from the roadmap (a scheduled run that reads the stage and its exit criteria) | Publishes the episode prepared on Sunday (≈ 15 min) |
| Monday–Thursday | Builds, runs the independent review, opens pull requests, runs CI, tags a pre-release, deploys it (from stage 2 to the home host in the staging role) | Answers decisions marked "proposed", if any |
| Thursday | Sends a "what to test this week" list to the author's bot; prepares the lesson post | Publishes the lesson post (≈ 5 min) |
| Friday–Sunday | — | Tests on the deployed instance (≈ 1–2 h) and sends voice notes with impressions to the bot |
| Sunday | Drafts the Monday episode — texts, numbers and talking points for the video — from the week's work and the author's notes | Records a 5–10 minute video with simple editing (≈ 30–45 min) |

**Where the author decides — always a human:**

1. Decisions marked "proposed" in [DECISIONS.md](DECISIONS.md).
2. Deploys that touch the author's real data (over SSH until stage 5, then the bot approval card).
3. Every publication: posts, videos and `DEVLOG.md` entries.

**Proposed:** code merges happen automatically when CI and the independent review pass, so the author is
never the bottleneck of the build; the author can stop the machine at any time. The scheduled driver is
set up when stage 0 starts. Expected author time: about 2–3 hours a week, more in the week the home host
moves to Linux (stage 2).

## Calendar (targets, not promises)

Each main episode reports the week's commitment against what actually happened. When work slips, the
dates move and the scope does not grow. Development starts only after the private v1's acceptance period
closes; if it closes later, the Season 1 dates shift by the same amount.

| Date (2026) | Slot | Episode | The work behind it |
|---|---|---|---|
| Tue 6 Oct | Launch | 0.1 How the plan was made | Requirements published; v1 under acceptance |
| Mon 12 Oct | Main | 0.2 Why CoFlow 2.0 is open source and not a product — and how this series works | v1 acceptance; no code yet |
| Thu 15 Oct | Lesson | 0.3 Twenty web pages, one used | — |
| Mon 19 Oct | Main | 1.0 Stage 0 starts: the commitments of the week; the machine takes the wheel | Stage 0 (after the v1 acceptance closes) |
| Thu 22 Oct | Lesson | 0.4 1,785 suggestions, 10 decisions | — |
| Mon 26 Oct | Main | 1.1 Stage 0: foundations and the delivery skeleton | Stage 1 starts |
| Thu 29 Oct | Lesson | 0.5 Where does a message go? | — |
| Mon 2 Nov | Main | 1.2 Stage 1: memory core, timeline and MCP | Stage 2 starts; the home host moves to Linux |
| Thu 5 Nov | Lesson | 0.6 233k rows under one lock | — |
| Mon 9 Nov | Main + review gate | 1.3 Stage 2: the bot, the daily rhythm and the home host | Stage 3 starts |
| Thu 12 Nov | Lesson | 0.7 Where $54.78 went | — |
| Mon 16 Nov | Main | 1.4 Stage 3: decisions and commitments | Stage 4 starts |
| Thu 19 Nov | Lesson | 0.8 Agents reviewing agents | — |
| Mon 23 Nov | Main | 1.5 Stage 4: sources | Stage 5 starts (two review rounds) |
| Thu 26 Nov | Lesson | 0.9 The system that always agreed with me | — |
| Mon 30 Nov | Main | 1.6 Stage 5 in progress: reliable execution | — |
| Thu 3 Dec | Lesson | 0.10 ∫G = V × E | — |
| Mon 7 Dec | Main | 1.7 Stage 5: meetings, the outbox and automatic rollback | Pre-releases run on the home host |
| Thu 10 Dec | Lesson | 0.11 Microservices or a modular monolith? | — |
| Mon 14 Dec | Main | 1.8 Two weeks on the home host: drills, what broke | Restore and rollback drills |
| Mon 21 Dec | Main | 1.9 The R1 release (target) | Tag `v2.0.0` |

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

## Season 0 — "What v1 taught me" (the launch, the first Monday, then the Thursday lesson posts)

| # | Episode | Source |
|---|---|---|
| 0.1 | How the plan was made: from v1, its usage data and its development history to the CoFlow 2.0 requirements — agents researching, critics reviewing, the owner deciding | [REQUIREMENTS.md](REQUIREMENTS.md), [DECISIONS.md](DECISIONS.md), [LESSONS_FROM_V1.md](LESSONS_FROM_V1.md) |
| 0.2 | Why CoFlow 2.0 is open source and not a product | [DECISIONS.md](DECISIONS.md) D-001, D-005 |
| 0.3 | Twenty web pages, one used: why the interfaces are a bot and MCP | [LESSONS_FROM_V1.md](LESSONS_FROM_V1.md) §1 |
| 0.4 | 1,785 suggestions, 10 decisions: why background queues die | §1 |
| 0.5 | Where does a message go? Routing between work and the private journal | §4 |
| 0.6 | 233k rows under one lock: SQLite with nine writers | §2 |
| 0.7 | Where $54.78 went, and why the prompt prefix sets the price | §7 |
| 0.8 | Agents reviewing agents: when to stop polishing | §8 |
| 0.9 | The system that always agreed with me: why an alignment check must be able to say "can't judge" | §7; [DECISIONS.md](DECISIONS.md) D-017 |
| 0.10 | ∫G = V × E: what can be measured between people, and what must be pre-registered | [REQUIREMENTS.md](REQUIREMENTS.md) §5.20 |
| 0.11 | Microservices or a modular monolith? Why one writer wins for a personal system | [DECISIONS.md](DECISIONS.md) D-030 |

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

On 9 November 2026 (after the fourth main episode), the author decides to continue, change or stop the
rubric based on:

- qualified replies: people who want to try CoFlow, contribute, or discuss decision systems;
- issues and discussions opened by others;
- reported installations after R1;
- the author's time per episode.

Reach (views, likes) is recorded but does not decide on its own.
