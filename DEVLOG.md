# DEVLOG

The canonical record of CoFlow 2.0's development, newest entry first. Every entry follows the episode
template in [docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md): Signal, Decision, Commitment, Action,
Tested, Outcome, Learning, Numbers, Artifacts.

Numbers are measured; an estimate is marked as an estimate. Failures are recorded with the same weight as
successes. Posts in other channels are short versions of these entries, and nothing here comes from the
author's private data beyond what the author selects for the episode — see the rules in
[docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md).

---

## Episode 0.2 — The harness today

*Season 0 · 15 October 2026 · video: <https://youtu.be/HC-rAElrr7k> (11:31)*

| Part | Content |
|---|---|
| Signal | The calendar had this week's episode announcing the start of stage 0. The private v1's acceptance period was still open, so stage 0 had not started and there was nothing built to report. Publishing a stage report with no stage behind it would have broken the one rule this series is about |
| Decision | Publish the episode anyway and report what is true: the system the author runs today, shown through one real decision instead of a tour of the tools. The weekly slot moves to Tuesday, where the series actually launched, and a video belongs to an episode only in the weeks that allow one (D-032) |
| Commitment | One episode a week; Season 1 dates shift by the week this cost, R1 target to 29 December |
| Action | Recorded in one take as a screen share with a camera inset, over a deck built for this episode, switching once to a second scene where photographs and clips from the fair played live rather than being cut in afterwards. Eleven and a half minutes of recording became an 11:31 video, with no editing pass. The episode walks one hypothesis end to end — "an exhibitor will buy the app on their stand, cold" — and then the four mechanisms that carried it: one id per person, topic and task across every system; a bot that prepares the context of a meeting before it starts; a meeting run from that brief, with the outcome returning to memory; and the record of the decision itself |
| Tested | The hypothesis was tested in the field at a trade fair, with the disproof criterion written down before the test. More than 100 conversations with exhibitors, by two people, every one of them recorded against the topic rather than a folder. Ten installs of the app came out of it; none of those ten used it even once, and reminders changed nothing — and that is after the app's entry flow was fixed in the field so that people could launch it at all |
| Outcome | The hypothesis is disproved and closed as disproved, from quotes rather than impressions, at the cost of two days at a fair instead of a quarter of building. What it leaves is uneven and the episode says so: the problem is real and confirmed, the moment is wrong (an exhibitor decides long before the fair, not on the floor), and the method is missing — getting the app installed is solved, getting it used is not. That is the next thing to test, not a conclusion |
| Learning | Write what counts as disproof before the test; afterwards there is always an explanation for why it nearly worked. An install is not a metric — use is. And an episode with nothing built is still an episode: reporting the gap honestly costs one week of dates and keeps the series worth reading |
| Numbers | More than 100 conversations in two days; 10 installs, 0 of them used; 20 slides; 11 minutes 31 seconds; no code in the repository yet |
| Artifacts | The video above · [BUILD_IN_PUBLIC](docs/BUILD_IN_PUBLIC.md) (the calendar after the shift) · [DECISIONS](docs/DECISIONS.md) D-032 |

## Episode 0.1 — How the plan was made

*Season 0 · 6 October 2026 · reports the work of 4 October 2026*

| Part | Content |
|---|---|
| Signal | Nearly five months of daily use of the private v1 — in use since mid-May 2026 — and its last 30 days of usage data: the Telegram bot used on all 13 days since it shipped on 22 September (138 incoming messages, 64 confirmed actions); 1,464 MCP calls on 12 days across 69 of its 96 tools; the 20-page web interface used about one hour in the whole month outside the recorder status page, with 6 pages not opened in 90 days; 10 of 1,785 background suggestions reviewed in the largest queue, 12 of 2,532 across all three; $54.78 of model API cost on a key shared with another of the author's apps, about $42 of it CoFlow's and about $25 of that one-off (archive processing and one evaluation run) |
| Decision | Make CoFlow 2.0 open source under Apache-2.0 (D-001) as a personal decision system rather than a product (D-005); write the requirements before any code and start building after the v1 acceptance period (D-004); start from a new clean repository, because v1's history cannot be published (D-003); freeze v1's features (D-006); develop in the open with the machine driving and the author deciding (D-032) |
| Commitment | A public requirements package the same day; development after the v1 acceptance period closes; one episode a week |
| Action | Agents read v1 — about 60k lines across 74 modules and the MCP server, 96 MCP tools, its development history and its incidents — and its usage data; researched deployment and CI/CD, Spanish tax and invoicing rules, architecture options and goal-setting methods; then wrote the documents. Independent critics reviewed after every step. The author answered the open questions in several short rounds and made every decision |
| Tested | Four rounds of independent review on 4 October. The final round raised 76 findings — 24 on internal consistency, 19 on what is safe to publish, 20 on whether the documents matched the author's actual decisions, 13 on the Spanish tax claims checked against official sources — all of them applied or carried into the open questions (REQUIREMENTS §8). Two further rounds ran before this entry was published, one on every number in it and one on publication safety and voice; their findings are in the text, including the numbers this entry corrects. A document check (`tools/check_docs.py`) verifies that every requirement and decision ID referenced in the repository resolves, that no ID is defined twice, and that every non-"Later" requirement outside the NFR group sits in a roadmap stage. No third-party personal data in the repository: the only name is the copyright line in NOTICE, and the author's own usage and cost figures are published by their choice |
| Outcome | Published: 14 principles and 191 prioritized requirements, a roadmap of stages 0–8, the architecture of a modular monolith, 41 module cards with acceptance thresholds, a deployment design, a decision log of 32 decisions — 19 accepted by the author and 13 waiting, with part of the detail still open inside seven of the accepted ones — the lessons from v1 and this build-in-public plan — the state at the time of this episode, with later additions reported in the episode of their week. No code yet: a plan, not a result |
| Learning | The agents recorded their own proposals as the author's decisions. In a decision system that is the failure the system exists to prevent: the decision survives and who made it is lost. The repository now separates "accepted" from "proposed" by rule, and the same rule is a requirement of the product (P-3, DEC-1). Usage data beat intuition: the interfaces that earned their place are the bot and MCP, and background queues were dropped. "Microservices" became a modular monolith with a quality gate per module (D-030). Legal research — a non-lawyer's reading, not legal advice — changed the scope: CoFlow registers invoices instead of issuing them (D-026) |
| Numbers | 26 agents; 4.48 million agent tokens measured across 23 of them, the other three unmeasured, so the real total is higher; the same calendar day from the open-source decision to the public repository; about 4,200 lines in `docs/`, 4,500 with the root documents; the author's time: answers to the open questions in several short rounds, not measured separately |
| Artifacts | [REQUIREMENTS](docs/REQUIREMENTS.md) · [ROADMAP](docs/ROADMAP.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [MODULES](docs/MODULES.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) · [DECISIONS](docs/DECISIONS.md) · [LESSONS_FROM_V1](docs/LESSONS_FROM_V1.md) · [BUILD_IN_PUBLIC](docs/BUILD_IN_PUBLIC.md) |

**Open question for anyone reading:** which decision of yours, in the last month, got lost between "we
decided" and "it got done"?
