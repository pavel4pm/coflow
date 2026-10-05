# DEVLOG

The canonical record of CoFlow 2.0's development, newest entry first. Every entry follows the episode
template in [docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md): Signal, Decision, Commitment, Action,
Tested, Outcome, Learning, Numbers, Artifacts.

Numbers are measured; an estimate is marked as an estimate. Failures are recorded with the same weight as
successes. Posts in other channels are short versions of these entries, and nothing here comes from the
author's private data beyond what the author selects for the episode — see the rules in
[docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md).

---

## Episode 0.1 — How the plan was made

*Season 0 · 6 October 2026 · reports the work of 4 October 2026*

| Part | Content |
|---|---|
| Signal | Nearly five months of daily use of the private v1 — in use since mid-May 2026 — and its last 30 days of usage data: the Telegram bot used on all 13 days since it shipped on 22 September (138 incoming messages, 64 confirmed actions); 1,464 MCP calls on 12 days across 69 of its 96 tools; the 20-page web interface used about one hour in the whole month outside the recorder status page, with 6 pages not opened in 90 days; 10 of 1,785 background suggestions reviewed in the largest queue, 12 of 2,532 across all three; $54.78 of model API cost on a key shared with another of the author's apps, about $42 of it CoFlow's and about $25 of that one-off (archive processing and one evaluation run) |
| Decision | Make CoFlow 2.0 open source under Apache-2.0 (D-001) as a personal decision system rather than a product (D-005); write the requirements before any code and start building after the v1 acceptance period (D-004); start from a new clean repository, because v1's history cannot be published (D-003); freeze v1's features (D-006); develop in the open with the machine driving and the author deciding (D-032) |
| Commitment | A public requirements package the same day; development after the v1 acceptance period closes; one episode a week |
| Action | Agents read v1 — about 60k lines across 74 modules and the MCP server, 96 MCP tools, its development history and its incidents — and its usage data; researched deployment and CI/CD, Spanish tax and invoicing rules, architecture options and goal-setting methods; then wrote the documents. Independent critics reviewed after every step. The author answered the open questions in several short rounds and made every decision |
| Tested | Four rounds of independent review on 4 October. The final round raised 76 findings — 24 on internal consistency, 19 on what is safe to publish, 20 on whether the documents matched the author's actual decisions, 13 on the Spanish tax claims checked against official sources — all of them applied or carried into the open questions (REQUIREMENTS §8). Two further rounds ran before this entry was published, one on every number in it and one on publication safety and voice; their findings are in the text, including the numbers this entry corrects. A document check (`tools/check_docs.py`) verifies that every requirement and decision ID referenced in the repository resolves, that no ID is defined twice, and that every non-"Later" requirement outside the NFR group sits in a roadmap stage. No third-party personal data in the repository: the only name is the copyright line in NOTICE, and the author's own usage and cost figures are published by their choice |
| Outcome | Published: 14 principles and 191 prioritized requirements, a roadmap of stages 0–8, the architecture of a modular monolith, 41 module cards with acceptance thresholds, a deployment design, a decision log of 32 decisions — 19 accepted by the author and 13 waiting, with part of the detail still open inside seven of the accepted ones — the lessons from v1 and this build-in-public plan. No code yet: a plan, not a result |
| Learning | The agents recorded their own proposals as the author's decisions. In a decision system that is the failure the system exists to prevent: the decision survives and who made it is lost. The repository now separates "accepted" from "proposed" by rule, and the same rule is a requirement of the product (P-3, DEC-1). Usage data beat intuition: the interfaces that earned their place are the bot and MCP, and background queues were dropped. "Microservices" became a modular monolith with a quality gate per module (D-030). Legal research — a non-lawyer's reading, not legal advice — changed the scope: CoFlow registers invoices instead of issuing them (D-026) |
| Numbers | 26 agents; 4.48 million agent tokens measured across 23 of them, the other three unmeasured, so the real total is higher; the same calendar day from the open-source decision to the public repository; about 4,200 lines in `docs/`, 4,500 with the root documents; the author's time: answers to the open questions in several short rounds, not measured separately |
| Artifacts | [REQUIREMENTS](docs/REQUIREMENTS.md) · [ROADMAP](docs/ROADMAP.md) · [ARCHITECTURE](docs/ARCHITECTURE.md) · [MODULES](docs/MODULES.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) · [DECISIONS](docs/DECISIONS.md) · [LESSONS_FROM_V1](docs/LESSONS_FROM_V1.md) · [BUILD_IN_PUBLIC](docs/BUILD_IN_PUBLIC.md) |

**Open question for anyone reading:** which decision of yours, in the last month, got lost between "we
decided" and "it got done"?
