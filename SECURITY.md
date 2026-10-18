# Security policy

## Status

Development started on 17 October 2026 (stage 0A, the decision core); there is no release yet. This
policy applies from the first pre-release.

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on this repository. Do not open a public issue.

Include what you found, how to reproduce it, and the impact you expect. Do not include real personal data,
real secrets or identifiers of your own infrastructure in the report.

You will get an acknowledgement within 7 days. Fixes are released as soon as practical, and the reporter is
credited unless they prefer otherwise.

## What CoFlow protects

CoFlow is a single-owner, self-hosted application. It runs on a host the owner controls (their own
computer, a home server or laptop, or a rented server), holds the owner's decisions, conversations,
commitments, money records and a private journal, and can act on the owner's behalf only after explicit
approval. The security model follows from that:

| Asset | Protection |
|---|---|
| Private journal | Never indexed, never exposed through tools, search or work answers. Sent to a model only by analysis modules the owner enables (journal switch, chosen at install); such calls are logged by hash, not text, and anything derived from journal input stays journal class. Canary tests run under both settings. Entries written through a messenger pass that messenger's servers; a way to write entries without a messenger exists |
| Conversations and people data | Stored on the owner's CoFlow host; text sent to the model provider for summaries and answers is listed in `DATA_FLOWS.md` and can be switched off |
| Money records | Amounts reach a model only per purpose and switch; tax figures never do; third-party tax ids and IBANs are masked; bank logins, API keys and certificates are never stored or sent. Tax outputs are estimates, not advice; CoFlow issues no invoices and files nothing (D-026) |
| External actions (calendar, messages) | Only through approval cards bound to a server-issued preview; executed once, only by the production instance; idempotent and verified |
| Secrets (API keys, bot token, OAuth tokens, messenger sessions, device tokens) | One store per instance; never in git, logs, the database, backups, images or CI logs; runtime tokens are re-created after a move or restore; encrypted at rest on the host and bound to its TPM where one exists; a revocation list generated from the inventory for a lost host or phone |
| Decision records | The basis is sealed when a decision is activated, so a later change shows as a new edition and a direct database edit is detected; a decision is private unless the owner publishes it, and one touching a third party's personal situation stays private |
| The host's disk | Full-disk encryption, required on a laptop host; firmware password, no USB or network boot |
| Text written by other people | Stored as untrusted external text: never an instruction, and withheld from cloud AI clients by default |
| MCP server and status page | Loopback or the container network by default; reachable from other owner devices only through a documented access recipe; a scoped token on every request; Host and Origin checks; every call logged. Internet-facing access for cloud AI clients comes later (stage-8 module 0) through a separate `edge` container behind the owner's relay, which never decrypts; read-only first, with other people's text withheld by default, pairing confirmed in the bot and an absolute grant lifetime |
| Telegram bot | Talks only to the owner's account in a private chat; one bot per instance; a second poller fences the instance, and a conflict fences it only when it repeats; high-risk approvals need a second factor, so a hijacked messenger session alone cannot approve; journal entries sent through the bot are deleted from the chat after ingestion |
| Releases | Built only by CI on GitHub-hosted runners from protected tags, signed, and verified by the host against one pinned identity before the owner approves the deploy; no CI credential reaches the owner's network |
| Remote administration | Key-only SSH over a private network with separate, hardware-backed keys per purpose and forced commands; the admin key is never available to AI coding tools; a second path inside the relay tunnel whose keys the relay does not hold |
| Real history before the switch-over | Only in a validation instance on the owner's machine until the decision adoption gate, with its data root outside any repository; it never acts outward, and CI and the evaluation harness refuse it. From the adoption, only on the host that passed its measured gate |

## Threat model in short

- **Trust zones.** The core runs on the owner's home host with its data and processing; apps with external
  users stay on their own platforms and are pulled read-only, never pushing into the home network; there
  is no shared server (D-051). The host runs the instance and nothing else.
- **Three ways in, one public.** The bot polls outbound; the owner's devices use an overlay VPN with SSH;
  only cloud AI clients need a public entry, and they get it later, through a relay that passes TLS
  through without decrypting into a tunnel the host opens, on a separate domain with DNSSEC and CAA
  (D-052, D-053). The `core` listener is never internet-facing.
- **The weakest places** are usually the development machine and the desktop messenger, not the host:
  they hold the keys and the messenger session that is the bot's owner channel, next to AI agents with
  access to files and the internet. They have their own baseline.
- **The baseline** that must hold before the first internet exposure — accounts and the domain, the host,
  the relay, monitoring and recovery, the bot and releases, and the owner's devices — is in
  [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) §8.3 and §8.4.
- **Accepted residual risks:** a cloud AI client's operator receives everything returned to it and holds
  a refresh token until the grant expires; the messenger sees what is written to the bot; a compromise of
  the running host is total (one writer on one host); a stolen powered-on host holds its disk key in
  memory; the DNS provider of the instance's domain is a root of trust; the relay's provider can deny
  service; the owner can approve a harmful but correctly signed release.

## Threats we treat as in scope

- **Prompt injection through third-party text.** Messages, emails, calendar titles, forwarded text, worker
  output and device-pushed text are data. They must not trigger tools, create rules or approve actions.
- **Approval forgery.** Any way to execute an external action or a production deploy without the owner's
  explicit approval bound to the previewed content.
- **Journal leaks.** Any path by which journal text, or output derived from it, reaches an index, a tool,
  a log, a work answer, a backup outside its policy, or a model call outside an enabled analysis module.
- **Secret leaks** into logs, the database, backups, images, CI output or error messages.
- **Network exposure.** Any listener reachable beyond loopback or the container network without the owner
  configuring a recipe; plaintext HTTP on any non-loopback address.
- **Supply chain and delivery.** A compromised dependency, base image, action or release identity reaching
  the host; code from fork pull requests reaching anything private.
- **A second writer.** Any way for a copy, a restore or a returning old host to act as production.
- **Stolen device or client tokens** used to push data that is then treated as the owner's own words.
- **Plugins** that exceed the data flows and permissions they declare, or open the database.
- **Consent phishing** through a cloud AI client that is shared by all users of its provider.
- **Exfiltration through third-party text** returned to a cloud AI client that also holds send-capable
  connectors.
- **A hijacked messenger session** approving high-risk actions.
- **Interception at the entry:** a relay, a DNS provider or a certificate authority that could read or
  redirect the owner's traffic.
- **A correctly signed but older or unreviewed release** reaching the host.
- **Real data in the wrong place:** a validation snapshot, a case script or its report reaching the
  repository, CI, an agent's memory or a host that has not passed its gate.

## Out of scope

- An attacker with the owner's unlocked device, or administrator access to the CoFlow host or to the
  hosting provider's console. Theft of a powered-on host is a residual risk that full-disk encryption does
  not remove.
- Security of third-party services (model providers, Telegram, Google, the VPN or backup provider) beyond
  how CoFlow uses them.
- Remote-access setups the owner configures outside the documented recipes.
- The relay's provider sees connection metadata (addresses, server names, timing, volumes) but no content;
  the DNS provider of the instance's domain is trusted for its records, monitored through certificate
  transparency.
