# Contributing to CoFlow

Thank you for your interest. CoFlow 2.0 is at the **requirements stage**: there is no code yet. The most
useful contributions right now are about what the system should do and why.

## How to take part now

- **Comment on the requirements.** Open a discussion or an issue that refers to a requirement ID from
  [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) (for example `MTG-5` or `P-3`).
- **Bring a use case.** Describe a real situation from your work — with invented names and data — where a
  personal decision system would help: the signal, the decision, the commitment, what went wrong.
- **Challenge a decision.** Every decision in [docs/DECISIONS.md](docs/DECISIONS.md) lists its
  alternatives. If you think another one is better, explain it with evidence.
- **Answer an open question** from REQUIREMENTS §8.

Code contributions open with stage 0 of the [roadmap](docs/ROADMAP.md), when the repository gets its
skeleton, test runner and CI. Until then, please do not send code pull requests.

## Rules for every contribution

- **Never post real personal data.** No real conversations, chat exports, recordings, names, phone numbers,
  email addresses or screenshots of real messages — not in issues, discussions, pull requests or test
  fixtures. Use invented examples.
- **Never post secrets or infrastructure identifiers.** API keys, bot tokens, OAuth files and session
  files stay on your machine or server — never in images, compose files, CI logs or issues; the same goes
  for your host names, addresses, domains and VPN or tunnel ids. If you posted a secret by mistake, revoke
  it first, then tell us.
- **English** for code, docs, issues and commit messages.
- **Security problems** are reported privately — see [SECURITY.md](SECURITY.md).

## Licence and sign-off

CoFlow is licensed under the [Apache License 2.0](LICENSE). Contributions are accepted under the same
licence.

Once code contributions open, every commit must carry a Developer Certificate of Origin sign-off
(`git commit -s`), which adds a line like:

```
Signed-off-by: Your Name <you@example.com>
```

By signing off you certify that you wrote the change or have the right to submit it under the project's
licence (see https://developercertificate.org/).

## What will be expected from code (from stage 0)

- Tests run offline: temp data folder, fake model provider, fake calendar and messenger, no network.
- No owner-specific literals in code, prompts, fixtures or deployment files; a test gate checks this.
- Every new data flow is declared in code and appears in `DATA_FLOWS.md`.
- Every module change keeps its module card ([docs/MODULES.md](docs/MODULES.md)) and acceptance suite green;
  a module never writes another module's tables.
- Every new feature has a user doc and a usage signal.
- Windows and Linux both pass in CI; the image is built on every pull request, and the suite plus a
  Compose smoke test (fakes, no egress) run inside it. Changes to the Dockerfile, Compose files or
  migrations need a passing upgrade test from the previous release.
- CI runs only on GitHub-hosted runners. Production deployment is never done by public CI, and no
  self-hosted runner is attached to this repository ([docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)).
