# Resolva

[![CI](https://github.com/Quentin-Guillerey/Resolva-/actions/workflows/main.yml/badge.svg)](https://github.com/Quentin-Guillerey/Resolva-/actions/workflows/main.yml)

**A self-maintaining, audit-ready, cross-departmental knowledge base — prototype.**

Resolva turns resolved support tickets into a shared, plain-English knowledge
base that every department can read, with an audit trail written for each entry
as it's created. It reads from the ticketing system only and never writes back,
so the source data stays clean.

> **Status: working prototype / portfolio demo.** The demo data is synthetic and
> sanitized. No production deployment, no measured outcomes, no performance
> claims. Items marked *roadmap* below are not built yet.

---

## What it does, in plain terms

A ticket gets resolved somewhere in the business. Resolva takes that resolved
ticket and:

1. **Strips the identity.** The customer's CRM id is converted into an internal
   6-digit account number and the CRM id is thrown away. The same customer
   always maps to the same number, but the number can't be turned back into
   anything the CRM would recognise — so a leak of the knowledge base exposes
   nothing actionable.
2. **Reads and sorts it.** A rule-based classifier tags the entry with a
   department and a sensitivity level (routine, cross-departmental, management,
   or legal). If the rules can't tell and you've added a Claude key, Claude is
   asked for a second opinion.
3. **Rewrites it for everyone.** Claude summarises the problem and the
   resolution into plain English any department can follow, and translates if
   the source was in another language. The **original record is kept attached**
   in its own language — the summary is a shared layer on top, not a replacement.
4. **Decides who signs off.**
   - **Auto-publish** — only for IT-closed, routine tickets with no further
     interaction. Straight into the knowledge base, with an automatic audit row.
   - **SME review** — anything cross-departmental, management-involved, or
     legal-adjacent waits in a queue for a department expert to check and
     approve. **Every legal-touching case is reviewed, no exceptions.**
5. **Logs it.** An append-only CSV audit row is written the moment an entry is
   published — automatically or by an SME — recording ticket number, date,
   sanitized account, description, resolution, time to resolve, stakeholders,
   whether validation was auto or manual, and comments.

The point of the prototype is to prove this whole loop end-to-end, at small
scale, with honest seams where a real deployment would go further.

---

## Run the web version (for the demo)

```
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>, click **Ingest → Load demo tickets**, then look at
the **Knowledge base**, **Review queue**, and **Audit log** tabs.

The web version exists so multiple departments could open it at once during a
demo. (Real multi-user accounts and login are *roadmap* — right now the SME's
name on the review screen is typed in, not verified.)

## Build the desktop version (same codebase)

The packaged build wraps the exact same app in a launcher that starts the server
and opens your browser, so a non-technical teammate just double-clicks an icon —
no Python needed on their machine.

```
pip install pyinstaller
pyinstaller resolva.spec
```

Output: `dist/Resolva` (a single executable). Build it on the operating system
you want to ship to — PyInstaller doesn't cross-compile, so build the Windows
`.exe` on Windows. (Same antivirus/SmartScreen caveats apply to an unsigned
internal build; check with IT before wide rollout.)

---

## Optional integrations (all off by default)

Open **Settings** in the app. Everything is optional and stored on that one
computer only (`%APPDATA%\Resolva\config.json` on Windows) — never bundled into
the app, never shared between teammates. There is no `.env` file.

| Setting | What it adds | Without it |
|---|---|---|
| **Anthropic API key** | Claude writes the plain-English summary, translates non-English tickets, and backs up the classifier | Summaries pass the raw ticket text through, clearly labelled; rules still classify |
| **Slack webhook** | Pings the SME when something lands in the review queue | Queue still works; you just check it manually |

The knowledge base (SQLite) and the audit log (CSV) live in that same per-user
folder, so they survive app updates.

---

## Where the data lives

| Thing | Format | Why |
|---|---|---|
| Knowledge base entries | SQLite (one file) | Needs to be searched, filtered, and edited during review |
| Audit trail | append-only CSV | A plain file an auditor can open in Excel, kept deliberately separate from the KB |
| Per-user config | JSON | Per-machine credentials, never bundled or shared |

---

## Tests & continuous integration

A small pytest suite covers the core loop. The tests run fully offline — no API
key, no network — so they're deterministic and free to run. They don't just
check that the app starts; they lock in the guarantees that make it audit-ready:

- the demo set splits exactly into auto-publish vs SME-review as intended,
- **nothing sensitive ever auto-publishes** — every auto entry is IT + routine,
- **every legal-touching ticket is held for review**,
- offline, the app reports that no AI summary was produced (no faked output),
- account numbers are decoupled, stable, and never contain the CRM id,
- the Flask routes respond and an SME approval writes a `manual` audit row.

Run them locally:

```
pip install pytest
python -m pytest -q
```

Every push and pull request to `main` runs the same suite on GitHub Actions; the
badge at the top of this file reflects the latest result.

---

## Project layout

```
resolva/
├─ app.py                 # Flask web app (routes)
├─ launcher.py            # desktop entry point: starts the server, opens the browser
├─ resolva/               # core logic (importable package)
│  ├─ config.py           # per-user settings (no .env)
│  ├─ accounts.py         # CRM id -> internal 6-digit account number (one-way)
│  ├─ classifier.py       # rule-based + AI-fallback department / sensitivity / routing
│  ├─ ai.py               # Claude summarize + translate (graceful offline fallback)
│  ├─ ingestion.py        # the pipeline: classify -> summarize -> route -> log
│  ├─ store.py            # SQLite knowledge base + review queue
│  ├─ audit.py            # append-only CSV audit trail
│  └─ notify.py           # SME Slack notification (optional)
├─ templates/             # HTML (dashboard, entry, review, ingest, audit, settings)
├─ static/style.css       # styling
├─ data/demo_tickets.csv  # sanitized, synthetic demo tickets
├─ tests/                 # pytest smoke tests
├─ .github/workflows/     # GitHub Actions CI
├─ resolva.spec           # PyInstaller build recipe
└─ requirements.txt
```

---

## What was reused from the CSR Automation Toolkit

Resolva is a separate system, but it deliberately carries over patterns already
proven in the toolkit (a single-team tool that's already built):

- the **CSV audit-log structure**,
- the **two-layer classifier** (rule-based first, AI only as a fallback),
- the **optional-integrations config pattern** (in-app settings, no `.env`),
- the **Slack alerting**, repurposed here as the **SME review notification**.

The toolkit's Tkinter desktop GUI did **not** carry over — Resolva is web-based.
Toolkit = a single team's proof of concept. Resolva = the cross-functional
system that extends that idea.

---

## Roadmap (not built yet)

- Live ticketing-system integration (prototype simulates the feed via CSV / manual intake).
- Real per-department SME accounts and authentication.
- Production-grade PII scrubbing on ingestion (demo data is pre-sanitized).
- Wider account-number space / mapping table to remove collision risk at scale.
- Asana / Zapier auto-routing for approved follow-ups (notification half is built).
- Measured outcomes once piloted: review load, auto vs manual split, audit coverage.

---

Built by **Quentin Guillerey** — operations / customer-experience background.
[LinkedIn](https://linkedin.com/in/quentin-guillerey)
