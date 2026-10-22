# Demonstration walkthrough

Date: 2026-10-23. Status: recorded and verified — the sequences below are the same steps the e2e demo spec executes against the real application; the recordings are its Playwright video output, not staged captures.

## Recordings

| Recording | Sequence | Source |
| --- | --- | --- |
| [01-correction-journey.webm](../demo/01-correction-journey.webm) | Diagnose → inspect → correct → undo/redo → save → revalidate → reopen → export | `apps/web/e2e/demo.spec.ts` test 1 |
| [02-accept-and-conflict.webm](../demo/02-accept-and-conflict.webm) | Clean validation → accept → two-session save conflict | `apps/web/e2e/demo.spec.ts` test 2 |

Reproduce locally:

```bash
cd apps/web
npx playwright test -c playwright.demo.config.ts
# videos land in test-results/demo-*/video.webm
```

The demo config builds the production bundle, serves it on :4173 and runs the real FastAPI backend against an isolated `.e2e-demo.db` — no mocks.

## Sequence 1 — the correction journey (corridor-a)

1. **Load evidence** — `corridor-a`, a labelled synthetic corridor. The diagnostic queue flags `S2` (`endpoint_mismatch`, +1.513 m) and `S4` (two residual issues — an honestly unresolved span).
2. **Inspect** — selecting S2 shows its predicted `attach_b` at z 10.50 against the observed pole top.
3. **Correct reversibly** — the endpoint is set to z 12; the journey explicitly demonstrates undo and redo before keeping the correction.
4. **Save durably** — Save commits the full constraint set as revision 1 in SQLite.
5. **Revalidate** — the run reports `succeeded at rev 1 — 2 issue(s)`: S2 resolved, S4's residuals remain flagged. Corrections never force a green result.
6. **Reopen** — after reload the saved constraint is the restored baseline (z 12.00, rev 1), not a lost draft.
7. **Export provenance** — `GET /review/export` followed by `POST /export/verify` reconstructs the declared constraints from the operation chain.

## Sequence 2 — acceptance and conflict (corridor-b)

1. **Validate clean** — corridor-b's predictions fit as extracted; a run at the initial revision reports 0 issues.
2. **Accept** — the clean run lets the reviewer accept the revision; the badge records it.
3. **Conflict** — a second browser session proposes a different B1 correction while session 1 saves first. Session 2's stale save is refused with the authoritative revision; its edit survives as an inspectable local change — nothing is silently overwritten.

## What the demo deliberately does not claim

- No electrical-safety certification — acceptance is workflow bookkeeping.
- S4's residual issues stay unresolved: the tool reports insufficient-evidence cases rather than clearing them.
- corridor-b contains no injected error, so sequence 2 shows clean acceptance rather than a fabricated correction.

## Neara alignment and portfolio positioning

The journey mirrors QA work a model-review engineer does on Neara-style digitisation output: algorithms may process successfully while producing incorrect network models, so the workbench provides spatial evidence inspection, reversible correction, validation and durable provenance. Within the portfolio, Cateniq demonstrates interactive 3D/spatial computation plus a reliable multi-user review workflow; NEMLab covers market analysis and Voltix simulated edge control. See [the project concept](../project-concept.md) for the full positioning statement.
