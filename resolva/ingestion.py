"""
Ingestion pipeline — the heart of Resolva.

For each resolved ticket:
  1. Sanitize the client id -> internal 6-digit account number (CRM id dropped).
  2. Classify: department, sensitivity, route (rule-based + optional AI fallback).
  3. Summarize/translate to plain English via Claude (or labelled passthrough).
  4. Route:
       auto   -> publish to the KB immediately + write an 'auto' audit row.
       manual -> hold in the SME review queue + notify the SME. The audit
                 'manual' row is written later, when the SME approves.
  5. The original source text is stored on the entry either way.

Resolva ingests only. It never writes back to the CRM — by design, to keep
the source clean.
"""

from datetime import datetime

from . import store, audit, ai, notify
from .accounts import to_internal_account
from .classifier import classify


def ingest_ticket(ticket: dict, cfg: dict) -> dict:
    """
    ticket keys (from CSV intake or manual form):
        ticket_number, client_id, description, resolution,
        time_to_resolve, stakeholders, source_language (optional hint),
        it_closed_no_followup (truthy/falsey)

    Returns a small result dict describing what happened.
    """
    account = to_internal_account(str(ticket.get("client_id", "")),
                                  cfg.get("ACCOUNT_SALT", "static"))

    ai_fn = (lambda t: ai.classify_department(t, cfg)) if cfg.get("ANTHROPIC_API_KEY") else None
    c = classify(ticket, ai_fn=ai_fn)

    summary = ai.summarize(ticket.get("description", ""),
                           ticket.get("resolution", ""), cfg)

    original_text = (
        f"DESCRIPTION:\n{ticket.get('description','')}\n\n"
        f"RESOLUTION:\n{ticket.get('resolution','')}"
    )

    entry = {
        "ticket_number": ticket.get("ticket_number", ""),
        "account_number": account,
        "department": c["department"],
        "departments_touched": c["departments_touched"],
        "sensitivity": c["sensitivity"],
        "source_language": summary["source_language"],
        "original_text": original_text,
        "summary_problem": summary["problem"],
        "summary_resolution": summary["resolution"],
        "time_to_resolve": ticket.get("time_to_resolve", ""),
        "stakeholders": ticket.get("stakeholders", ""),
        "validation_process": "auto" if c["route"] == "auto" else "manual",
        "classifier_reason": c["reason"],
    }

    if c["route"] == "auto":
        entry["status"] = "published"
        entry["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_id = store.add_entry(entry)
        audit.write_audit({
            "ticket_number": entry["ticket_number"],
            "account_number": account,
            "description": summary["problem"],
            "resolution": summary["resolution"],
            "time_to_resolve": entry["time_to_resolve"],
            "stakeholders": entry["stakeholders"],
            "validation_process": "auto",
            "comments": c["reason"],
        })
        return {"entry_id": entry_id, "route": "auto", "department": c["department"],
                "sensitivity": c["sensitivity"], "reason": c["reason"],
                "ai_used": summary["ai_used"]}

    # manual path
    entry["status"] = "pending"
    entry_id = store.add_entry(entry)
    notify.notify_sme(cfg, ticket_number=entry["ticket_number"],
                      department=c["department"], sensitivity=c["sensitivity"],
                      reason=c["reason"])
    return {"entry_id": entry_id, "route": "manual", "department": c["department"],
            "sensitivity": c["sensitivity"], "reason": c["reason"],
            "ai_used": summary["ai_used"]}


def approve_review(entry_id: int, problem: str, resolution: str, reviewed_by: str):
    """SME approves a queued entry: publish it and write the 'manual' audit row."""
    store.update_review(entry_id, problem, resolution, reviewed_by, "published")
    e = store.get_entry(entry_id)
    audit.write_audit({
        "ticket_number": e["ticket_number"],
        "account_number": e["account_number"],
        "description": problem,
        "resolution": resolution,
        "time_to_resolve": e["time_to_resolve"],
        "stakeholders": e["stakeholders"],
        "validation_process": "manual",
        "comments": f"Reviewed by {reviewed_by}. {e['classifier_reason']}",
    })


def reject_review(entry_id: int, reviewed_by: str):
    store.update_review(entry_id, "", "", reviewed_by, "rejected")
