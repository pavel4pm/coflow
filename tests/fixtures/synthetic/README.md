# Synthetic fixtures

Everything in this folder is invented. No real person, company, conversation, decision title,
number, address or host appears here, and nothing here was copied from a real system and then
edited. The literal gate (`tools/literal_gate.py`) scans these files for e-mail addresses, phone
numbers, domains, IP addresses, private host names and person-like names.

## The fixture world

Every suite shares one small world, defined by the decision-core design (§9.1) and the shared test
fixtures in `tests/conftest.py`:

- the owner: display name "Owner", zone `Europe/Berlin`, a fake clock at 2026-11-15T09:30:00.000Z
  (10:30 local time on 15 November 2026);
- foreign people `V1_P901` ("Person A") and `V1_P902` ("Person B");
- goals `V1_G901` "Cut fixed costs" (dropped on 2026-11-05) and `V1_G902` "Grow the training line"
  (active);
- the synthetic snapshot family S1, S1′ and S1″ in `snapshots/`: v1 numbers 903 to 910, with 901
  and 902 deleted without trace.

## Rules

- **Append only.** Tracks add files; they do not change or delete another track's fixtures. A
  fixture that must change gets a new file name.
- **Synthetic by construction.** Snapshots carry `"synthetic": true`. Names follow the conventions
  in [`allowed_names.txt`](allowed_names.txt) ("Person A", "Owner", "Example ... Ltd"); a new
  invented name that the gate flags is appended there, never a real one.
- **Sentence case.** Titles are written in sentence case ("Cut fixed costs"), so the name check
  stays quiet without an allow-list entry.
- **No real data, ever.** The owner's real snapshot, case scripts and case reports live in the
  validation data root outside any repository working tree, and never here.

## Layout

| Path | Owner | Content |
|---|---|---|
| `snapshots/` | track S | `coflow.import.decisions` v1 files: S1, S1′, S1″ and planted variants |
| `allowed_names.txt` | shared | the invented names fixtures may use |

The format's own synthetic example lives with its schema in
`src/coflow/contracts/examples/`.
