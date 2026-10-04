# Lessons from v1

The private v1 has run the author's working life since spring 2026: Streamlit and SQLite, a Telegram bot,
an MCP server with 96 tools, local transcription, about 47k lines of Python written mostly by coding
agents. This page collects what it taught — incidents, numbers and the rules they produced. Every lesson
points to the requirement it became in [REQUIREMENTS.md](REQUIREMENTS.md).

Numbers are aggregates from the author's own instance. No personal or third-party data is published.

## 1. What people actually used

- **One web page out of twenty.** Of 20 web pages, one was really used — the directions board, about 11
  hours since May. In the last 30 days the whole web interface, apart from the recorder status page, was
  used for about an hour; six pages were not opened in 90 days. Of 48 task fields, 7 were used; 752 of 996
  task comments were written by machines. → D-009, UI-1, P-13.
- **The bot and MCP carried the work.** 138 messages to the bot on 13 of 13 days; 1,464 MCP calls on 12
  days, 69 of 96 tools used. → BOT-*, MCP-*.
- **Background suggestion queues were not reviewed.** Recording links: 10 of 1,785 decided. Contacts: 2 of
  383. Commitments from chats: 0 of 364. Paid suggestions nobody reads are a cost and a lie about
  coverage. → CMT-2, P-13.
- **Cards in the conversation do get decided.** Of 43 approval cards in the bot, 34 were executed and 5
  cancelled. These were changes the owner had asked for, so they prove the card mechanism, not that
  unsolicited proposals would be read. That is why proposals in v2 are capped, measured and switch
  themselves off (CMT-2).
- **Built but never used:** leads and outreach, strategy editing, the knowledge graph. A generic link
  graph held 0 links three months after it was built: links get filled only where a process forces it.
  Speaker diarization was tried once on real recordings and switched off (§6). → REQUIREMENTS §7.

## 2. SQLite under many processes

- **Search triggers held the write lock.** Index triggers deleted rows by unindexed columns, so every
  message update scanned ≈ 233k rows under the write lock; with nine writing processes, others timed out
  and crashed. Fix: deterministic index row ids (kind code × 10¹² + id). A message update went from 0.43 s
  to 0.02 s. → SRC-2.
- **Model calls inside write transactions.** Computing inside a transaction held the lock for seconds.
  Rule: compute first, then write briefly. → OPS-3.
- **Start-up writes.** Every process wrote schema checks on start; service marks crashed processes after a
  30-second wait. Fix: initialise once per code and schema revision, soft writes with retries, a watchdog
  that logs writers holding the lock for more than 10 seconds. → OPS-3.
- **Old code in long-lived processes.** An AI client kept an old server process alive for days; after a
  deployment it rebuilt the whole index (25–50 s) and restored old triggers. Fix: a frozen index version
  key, explicit rebuilds only, processes on old code refuse maintenance, restarting every process after a
  deployment. → OPS-3, DEP-9.
- **Silent loss in full-text insert.** An insert without an explicit row id was overwritten by the next
  one. Fix: explicit row ids always. → SRC-2.
- **Tests checked a different schema.** The schema was applied after migrations, so on a clean database
  migrations were skipped and tests ran against a schema that production did not have. → OPS-4.
- **Case-insensitive search failed for Cyrillic.** SQLite's `LOWER()` is ASCII-only: duplicate people,
  missed aliases. → SRC-1.

## 3. Identity and numbering

- **Direct inserts bypassed the numbering tap**: 59 people and 58 companies ended up without numbers. →
  IDN-1.
- **"max + 1" under concurrency** issued the same number twice. Fix: an immediate write transaction and a
  test with 6 threads × 40 issues. → IDN-1.
- **Two writing copies of the database** drifted apart; 17 company numbers collided. → P-1.
- **An external registry issued its own numbers**; counters had to be shifted by hand. One tap, no
  exceptions. → IDN-1.
- **Matching people by name** created a duplicate person. Rule: strong keys (messenger id, email, phone),
  never a message by name; ambiguity returns candidates and creates nothing. → IDN-3.
- **36 of 492 files were duplicates by content.** Identity of a file is its content hash. → IDN-6.

## 4. Privacy

- **The journal reached a model without a switch.** In May, 18 model calls received journal text through
  no path the owner had enabled, and the call log kept full prompts forever. Fix: journal flows only
  through an explicit switch (D-025), canaries on every channel, prompt retention limits. → P-2, PRV-3,
  PRV-9, NFR-6.
- **The bot routed everything to the journal.** An evening review would have landed in the private
  journal. Fix: work by default, journal only by explicit marker, buttons when in doubt, three review
  rounds with canaries over every message path. → D-012, BOT-2.
- **"Move to journal" first edited text inside other records.** Fix: blank whole derived records only, and
  say honestly that a paraphrase in other words cannot be found. → BOT-3.
- **The network MCP checked its token only at start**, and its port collided with another service. Fix
  (in v1): a token on every request, loopback only, a read-only mode. → MCP-1.
- **The bot token reached a log file.** → PRV-4.
- **The bot evaluation could overwrite live backups** and call the real calendar with real tokens. Fix in
  v2: tests and evaluations run on temp data with fake providers and no network. → OPS-8.

## 5. Writing to the outside world

- **Done before it was done.** A meeting with a calendar event was marked done even when the calendar call
  failed; a one-off event had no own id, so a retry could duplicate it and resend invitations. → D-011,
  MTG-5.
- **What worked:** the week plan used deterministic event ids, conditional writes, and a read-back by id
  after a lost response; an event counted as its own only when label, organizer and id matched, and a slot
  the owner dragged by hand was never moved back. Repeating an approval created 0 new events. → P-8,
  MTG-11.
- **Labels must survive the provider's search.** Calendar search does not split words on underscores, and a
  Cyrillic letter does not match its Latin twin. Labels are Latin, space-separated. → IDN-7.
- **Two "free slot" rules.** The bot and the AI chat proposed different free slots. Fix: one busy rule,
  exactly as the calendar provider reports it. → MTG-6.
- **An event title could imitate an approval card.** Third-party text is data. → P-10.
- **Re-login must never start by itself**: an OAuth client has a limit of refresh tokens per account, and a
  silent loop burns it. → SIG-9.

## 6. The recorder pipeline

- **An hour-long recording ran out of memory** (voice detection on float64 audio ≈ 1 GiB). Fix: chunks at
  silences, a memory check before transcription, smaller chunks on retry. → SIG-3.
- **A temporary failure became permanent, and the bot was silent.** In a live run, the system did 4 of
  about 12 steps by itself. Fix: transient vs. final errors, scheduled retries, a visible "why it waits".
  → SIG-3, OPS-6.
- **A WAV file without a header**: about 106 minutes lost, the rest recovered from matching channels. →
  SIG-3.
- **Moving files in one transaction left half-states.** Rename on disk first, then in the database. →
  NFR-8.
- **Diarization on real recordings found one speaker in a dialogue** (the "stereo" was fake). Wrong labels
  are worse than none. → SIG-12, D-013.
- **What worked:** a small multilingual model on CPU (int8) transcribed about 650 hours of archive; the
  summaries of that archive cost ≈ $17. → SIG-2.

## 7. Cost and quality of model answers

- **$54.78 in 30 days** on a key shared with another of the author's apps: one-off archive processing
  ≈ $17, one evaluation run ≈ $8, bot answers ≈ $11, the other app ≈ $13, background work ≈ $6–7. Input
  tokens outnumbered output tokens about 25 to 1: the system reads much more than it writes. → OPS-7.
- **The prompt prefix sets the price.** A bot answer averaged 47k input tokens: tools returned raw vectors
  and every session of a person, and the chat was re-summarised on every message. A compact mode with
  dossiers (L0–L3) cut cost by 37% and was better in evaluation (recall 0.69 vs. 0.59–0.64; correct
  actions 9 of 10 vs. 5–7 of 10). → P-7, BOT-4.
- **Prompt caching and correct price tables matter.** Without caching, one answer of the largest model
  cost $1.19; with caching about $0.45. The price table in code was wrong. → OPS-7.
- **A good long summary could be overwritten** by a truncated one with the same version mark. Fix:
  provenance with the input hash and prompt version. → P-7.
- **"Not found" was a lie about coverage.** The bot did not find an address because only half of the
  history was loaded and the address was a map link. Fix: rule-based entities and explicit coverage. →
  SRC-3, P-9.
- **A judge that cannot say "can't judge".** A compliance engine scored conversations against the
  owner's principles and never once returned "violation". Even "uncertain" had to carry a number, so it
  could not say "can't judge"; and its prompt received only the first file of a recording. → P-6.
- **Ranking by the next-step date** pushed months-old sales leads above a planned trip. The morning plan is
  a deterministic ranking with reasons. → RHY-1.
- **Activity rules by program name** labelled 178 of 198 minutes as drift that was not drift. → plugin,
  measured before use.

## 8. Operations and process

- **A PID file** was reused by another process after a crash, and the worker never started again. Fix:
  locks held by the operating system. → OPS-2.
- **Windows scheduler jobs** were created by hand (11 of them); a log opened for appending blocked a second
  instance; non-ASCII characters in a batch file broke a scheduler command. Fix in v2: one supervisor
  process. → OPS-2, D-008.
- **Restore was never tested**, and all backups were on the same disk. → OPS-5.
- **A stale tool map is worse than none**; AI clients read the tool list once at start. Fix: a catalogue
  generated from code and checked in CI. → MCP-3.
- **Mixed UTC and local time** moved an evening's closed day into the next day. → MTG-7.
- **Reading must not write.** Opening a tab created empty day records. → NFR-8.
- **Agents reviewing agents always find something.** Independent review rounds found 33, 46, 50 and 83
  remarks; one small button went through five rounds. Rule: one review round per stage, two when the stage
  writes to the outside world or builds a money module; leftovers become issues. → ROADMAP "How a stage runs".
- **Parallel agent sessions issued the same version numbers.** Releases are tagged from one place.
- **An internet provider blocked a CDN's address ranges on some days.** A failure is logged once and
  retried in the next cycle, not reported every minute. → BOT-5.

## 9. A home server without operations

- **A separate home server ran production for about two months and was given up.** It could be
  administered only physically: no remote desktop, no SSH, no admin share (that server is being retired).
  The documented remote-access
  path was never configured, and deployment was a manual pull plus a script. → D-019, DEP-9, DEP-11,
  DEP-12.
- **The colliding numbers came from the dev/prod split itself.** The dev machine kept a writable copy
  while the server held production; a numbering migration ran on the dev copy while production kept
  receiving records. → P-1, DEP-2, DEP-3.
- **The old production was never retired.** A month after moving back it still ran the web app and a
  network MCP — a second write point that only switching the machine off stopped. → DEP-3, DEP-18.
- **Docs drifted from reality.** Several files described remote access through a tunnel that had never
  been set up; only the overlay VPN worked. Deployment state must come from health output, not prose. →
  DEP-12.
- **The server was run like a desktop app:** a laptop, start at user logon, console windows, services
  stopped when the lid closed; the calendar copy went stale whenever the machine slept. → OPS-2, DEP-14.
- **Credentials were bound to one machine and one OS user**, and nothing listed which ones; moving
  machines meant issuing them again by memory. → SIG-9, PRV-4, DEP-18.
- **Remote MCP on the server was protected by a token checked only at start.** v2 checks a token on every
  request, binds only to configured interfaces and enables DNS-rebinding protection. → MCP-1.
- **Recordings were too big for the tunnel's request limit**, and a cross-disk move in one transaction left
  partial copies. → SIG-2, DEP-16.
- **Nothing reported a dead bot or server,** because every status output came from the machine itself. →
  OPS-6 (an off-host heartbeat).
