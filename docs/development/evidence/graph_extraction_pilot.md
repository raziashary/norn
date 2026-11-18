# P06-T02 relation extraction pilot (development, pilot role, seed 47)

Scope: development label `DEVELOPMENT_PILOT_ROLE; NOT_A_CONFIRMATORY_RESULT`. Pilot role only (24 clusters,
48 cases per stratum, six families M1 to M6), single seed, single run. No tune or evaluation read, no
model, no network, no Groq call. Evidence entry: E-P06-009 in `EVIDENCE_LOG.md`.

## Command and artifact

```text
.venv/Scripts/python.exe -m benchmark.runs.cli graph-extraction-report \
    --output .norn/p06-t02-extraction-report.json --work-dir .norn/p06-t02-work --seed 47
```

- Report `.norn/p06-t02-extraction-report.json` (ignored, not committed), sha256
  `d21f8412f75c011d6a054ed3ff00a2922e25546d3e681d4515e64dc2102d6276`.
- Code digest at run time `8beba0b7cf037357fe29b191d5a78a83ad7ec05f6614ca825fa9819e11f4f9b7`.
- One throw-away store per (track, case), removed after scoring; the work directory is empty afterwards.

## Tracks

| Track | Stratum | What it reads | Role |
|---|---|---|---|
| `TEMPLATE_READBACK` (`relations-readback-v1`) | TEMPLATE | the canonical atom (predicate `requires`, stored value) | zero-extraction-error control |
| `NOISY_TEXT` (`relations-text-v1`) | TEMPLATE, NOISY_V1 en, id, mixed | only the `message` of the stored source text | the realistic derived track |
| `GOLD_DIAGNOSTIC` (`gold-diagnostic-v1`) | TEMPLATE | edges written from the hidden gold graph | unequal oracle upper bound, never scored as a derived track |

An edge is the triple (tail governed key, head governed key, relation). A derived edge never carries a
hidden id. The scorer refuses an oracle-revision edge in a derived track and an unlabelled edge in the
oracle track.

## Results (pooled over the 48 pilot cases of each stratum)

Every track has 855 derived edges, 0 false positives, 0 unkeyed edges, citation agreement 1.0.

| Pool | Gold | True positive | Precision | Recall |
|---|---:|---:|---:|---:|
| strict (all gold edges stated by a published source) | 1,029 | 855 | 1.000 | 0.831 |
| representable (gold edges whose two keys a published source defines) | 855 | 855 | 1.000 | 1.000 |

The strict and representable figures are identical on all six track and stratum cells.

The 174 strict misses are not reading errors. They are gold edges with an endpoint key that no published
source defines, so the identity policy (T17, a keyed entity exists only where a source defines its key)
gives the edge nothing to attach to. Per family (TEXT/TEMPLATE): M1 5, M2 5, M3 159 (the hub key is defined
only by the source the missing variant drops), M4 5, M5 0, M6 0. The skip counts (`UNRESOLVED_ENDPOINT`) equal
these 174 edges. Gold edges that only an unpublished private source states are counted apart: M1 5, M2 5,
M3 5, M4 25.

Identity side check (pooled, TEXT/TEMPLATE): alias links 10 against 10 gold alias links, 0 unresolved,
registered keys 1,712 against 1,742 gold keys (30 undefined by any published source), 0 unknown registered
keys.

## What this does and does not show

- The three tracks agree edge for edge on every pilot case, so the derived graph reproduces the supported
  gold graph from the published sources with the extraction limits listed here. The speculation rule is
  proven on constructed sources only: no fixture contains a hedged or causal clause.
- The text reader's grammar was written from the same phrasing families that the NOISY_V1 renderer uses.
  Perfect noisy recall therefore measures tolerance of one adjacent-letter swap, the listed abbreviations
  and the en and id wording, not open-domain extraction. Documented misses, each tested: synonyms such as
  "relies on", deleted letters, two edits in one word, long gaps between the two identifiers.
- The capture of a NOISY_V1 source still carries the clean fact. The text track ignores it by design; the
  read-back track on a noisy rendering would read the clean capture and was not run.
- A display name in a clause is not verified against a keyless stating entity (it is checked only when the
  entity has labels). The hedge window of four tokens before the first identifier can cross a sentence
  boundary.
- Single seed, pilot role, development label; no interval is reported. Zero observed false positives are not
  zero risk.
- The attested T20 run (`.norn/p06-t20-run-001`) is bound to its code digest, which T01 and T02 changed, so
  `multihop-report` fails with `RUN_CODE_MISMATCH` at this commit and reloads only at commit `9b6e6f1`.
