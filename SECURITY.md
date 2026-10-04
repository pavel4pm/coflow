# Security policy

## Status

CoFlow 2.0 has no released code yet. This policy applies from the first pre-release.

## Reporting a vulnerability

Please report vulnerabilities **privately** through GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on this repository. Do not open a public issue.

Include what you found, how to reproduce it, and the impact you expect. Do not include real personal data,
real secrets or identifiers of your own infrastructure in the report.

You will get an acknowledgement within 7 days. Fixes are released as soon as practical, and the reporter is
credited unless they prefer otherwise.

## What CoFlow protects

CoFlow is a single-owner, self-hosted application. It runs on a host the owner controls (their own
computer, a home server or a rented server), holds the owner's conversations, commitments, money records
and a private journal, and can act on the owner's behalf only after explicit approval. The security model
follows from that:

| Asset | Protection |
|---|---|
| Private journal | Never indexed, never exposed through tools, search or work answers. Sent to a model only by analysis modules the owner enables (journal switch, chosen at install); such calls are logged by hash, not text, and anything derived from journal input stays journal class. Canary tests run under both settings. Entries written through a messenger pass that messenger's servers; a way to write entries without a messenger exists |
| Conversations and people data | Stored on the owner's CoFlow host; text sent to the model provider for summaries and answers is listed in `DATA_FLOWS.md` and can be switched off |
| Money records | Amounts reach a model only per purpose and switch; tax figures never do; third-party tax ids and IBANs are masked; bank logins, API keys and certificates are never stored or sent. Tax outputs are estimates, not advice; CoFlow issues no invoices and files nothing (D-026) |
| External actions (calendar, messages) | Only through approval cards bound to a server-issued preview; executed once, only by the production instance; idempotent and verified |
| Secrets (API keys, bot token, OAuth tokens, messenger sessions, device tokens) | One store per instance; never in git, logs, the database, backups, images or CI logs; runtime tokens are re-created after a move or restore |
| MCP server and status page | Loopback or the container network by default; reachable from other owner devices only through a documented access recipe; a scoped token on every request; Host and Origin checks; every call logged |
| Telegram bot | Talks only to the owner's account in a private chat; one bot per instance; a second poller fences the instance |
| Releases | Built only by CI on GitHub-hosted runners from protected tags, signed, and verified by the host against one pinned identity before the owner approves the deploy; no CI credential reaches the owner's network |
| Remote administration | Key-only SSH over a private network with separate keys per purpose and forced commands; the admin key is never available to AI coding tools |

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

## Out of scope

- An attacker with the owner's unlocked device, or administrator access to the CoFlow host or to the
  hosting provider's console. Theft of a powered-on host is a residual risk that full-disk encryption does
  not remove.
- Security of third-party services (model providers, Telegram, Google, the VPN or backup provider) beyond
  how CoFlow uses them.
- Remote-access setups the owner configures outside the documented recipes.
