# Agent tooling note — non-BMP emoji corruption in file-edit tools

Recorded: 2026-10-22
Scope: known failure mode of the coding-agent file tools when writing
4-byte (non-BMP) Unicode characters, with diagnosis evidence and the working
mitigation. Not part of the Cateniq application; retained so future sessions
do not re-debug this. Adapted from the Voltix project's
`docs/project/agent-tooling-notes.md` (sibling repository), where the same
failure was first diagnosed on 2026-10-12.

## Symptoms observed

- 2026-10-22, this repository: an `edit` call flipping the CAT-003 index icon
  in `docs/project/backlog.md` wrote `�` (U+FFFD) where `🚧` (U+1F6A7) was
  intended; the follow-up `edit` was then interrupted and the user repaired
  the line manually.
- Voltix sessions observed the same corruption on `🟢` (U+1F7E2) and repeated
  edit stalls ("Canceled due to user interrupt") around status-emoji changes.

## Root cause — byte-level evidence

The `edit` tool corrupts 4-byte UTF-8 characters on write: `f0 9f 9f a2`
(`🟢`) lands on disk as `ef bf bd` (`�`, U+FFFD). The `write` tool was also
implicated in earlier Voltix failures. `xxd` on the repaired Cateniq backlog
line shows the correct `f0 9f 9f a2` sequence for `🟢`.

Status icons in the Cateniq backlog:

| Emoji | Code point | UTF-8 bytes | Risk via `edit`/`write` |
| --- | --- | --- | --- |
| `✅` | U+2705 | `e2 9c 85` | BMP (3-byte) — writes correctly |
| `⛔` | U+26D4 | `e2 9b 94` | BMP (3-byte) — writes correctly |
| `🟢` | U+1F7E2 | `f0 9f 9f a2` | 4-byte — observed corrupting |
| `🚧` | U+1F6A7 | `f0 9f 9a a7` | 4-byte — observed corrupting |
| `📋` | U+1F4CB | `f0 9f 93 8b` | 4-byte — at risk |
| `🗑️` | U+1F5D1 + U+FE0F | `f0 9f 97 91 ef b8 8f` | 4-byte — at risk |

Four of the six status icons are non-BMP. Treat every 4-byte character as
unsafe in `edit`/`write` payloads — including inside `old_string` match
text, where a corrupted match can silently fail or write `�`. BMP
punctuation (`—`, `–`, `×`, `→`) and BMP emoji write correctly.

## Mitigation

1. Route any write containing non-BMP characters through a scripted write
   instead of `edit`/`write`. Python emits correct UTF-8:

   ```bash
   python3 - <<'PY'
   from pathlib import Path
   p = Path("docs/project/backlog.md")
   s = p.read_text()
   s = s.replace("Status: Ready 🟢", "Status: In progress 🚧", 1)
   p.write_text(s)
   PY
   ```

   `printf`/`cat >>` heredocs and `sed`/`perl` also write correct UTF-8.
   Edits whose `old_string` and `new_string` are pure ASCII or BMP-only are
   safe through `edit`.
2. A status flip touches two places — the task's `Status:` line and the
   index icon. Do both in one scripted write so they cannot drift.
3. After any document write containing non-BMP characters, verify:

   ```bash
   grep -rn $'\xef\xbf\xbd' docs/     # expect no output
   grep -n "🟢" docs/project/backlog.md | head
   sed -n '<line>p' docs/project/backlog.md | xxd   # expect f0 9f 9f a2
   ```

## Permission-prompt factor (from the Voltix notes)

In Devin's Normal permission mode each `edit`/`write`/`exec` call prompts,
and a declined prompt cancels the remaining queued calls — this produced the
"stuck agent" appearance alongside the corruption. Scripted `exec` writes
avoid that queue. The repository `project-management` skill auto-approves
`edit` and `exec`, but the byte corruption is independent of prompting —
use scripted writes regardless.

## Residual notes

- A separate stale-editor-buffer fault was seen in Voltix: tool reads showed
  new content while the compiler saw the old file. Unrelated to emoji, but
  worth remembering if a file appears not to update.
- Verification baseline for this note: `grep -rn` for U+FFFD over `docs/`
  returned zero hits and `xxd` showed `f0 9f 9f a2` for `🟢` on 2026-10-22.
- Linked from `AGENTS.md`, the `project-management` skill and
  `docs/project/documentation-guide.md`.
