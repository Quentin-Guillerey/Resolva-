"""
Smoke tests for Resolva's core loop.

These run fully offline (no API key, no network): the classifier is
deterministic, Claude summarization falls back to a labelled passthrough, and
the knowledge base / audit log write to a temp folder set up in conftest.py.

The point is to lock in the guarantees that matter for an audit-ready tool:
nothing sensitive auto-publishes, every legal case is held for review, the
offline path is honest about not using AI, account numbers are decoupled, and
the audit trail records both auto and manual validations.
"""

import csv
import os

from resolva import config, store, ingestion, audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "data", "demo_tickets.csv")


def _reset():
    """Fresh, empty knowledge base + audit log for each test."""
    for p in (config.db_path(), config.audit_path()):
        if p.exists():
            p.unlink()
    store.init_db()


def _load_demo():
    cfg = config.load()
    with open(DEMO, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["it_closed_no_followup"] = str(
            row.get("it_closed_no_followup", "")
        ).strip().lower() in ("yes", "true", "1")
        ingestion.ingest_ticket(row, cfg)
    return rows


def test_demo_splits_5_auto_6_manual():
    _reset()
    _load_demo()
    c = store.counts()
    assert c["published"] == 5, c
    assert c["pending"] == 6, c


def test_nothing_sensitive_auto_publishes():
    _reset()
    _load_demo()
    # Anything that published automatically must be the safe case only:
    # IT department, routine sensitivity, auto-validated.
    for e in store.list_published():
        assert e["validation_process"] == "auto"
        assert e["sensitivity"] == "routine"
        assert e["department"] == "IT"
    # And nothing legal may ever be live without a human.
    assert all(e["sensitivity"] != "legal" for e in store.list_published())


def test_legal_tickets_are_held_for_review():
    _reset()
    _load_demo()
    legal_pending = [e for e in store.list_pending() if e["sensitivity"] == "legal"]
    assert len(legal_pending) >= 2  # the two legal demo tickets


def test_offline_summary_is_honest_passthrough():
    _reset()
    cfg = config.load()  # no API key in CI -> offline
    res = ingestion.ingest_ticket({
        "ticket_number": "TK-TEST", "client_id": "Z999",
        "description": "Mower will not return to the dock to charge.",
        "resolution": "Reseated the charging contacts; charging resumed.",
        "it_closed_no_followup": False,
    }, cfg)
    # Offline, we must NOT claim an AI summary was produced.
    assert res["ai_used"] is False


def test_account_number_is_decoupled_and_stable():
    cfg = config.load()
    from resolva.accounts import to_internal_account
    salt = cfg["ACCOUNT_SALT"]
    a = to_internal_account("A100", salt)
    assert a == to_internal_account("A100", salt)   # same client -> same number
    assert a != to_internal_account("A101", salt)   # different client -> different
    assert len(a) == 6 and a.isdigit()              # 6-digit internal id
    assert "A100" not in a                          # not the CRM id itself


def test_flask_routes_respond():
    _reset()
    _load_demo()
    import app as appmod
    client = appmod.app.test_client()
    for path in ["/", "/review", "/audit", "/settings", "/ingest"]:
        assert client.get(path).status_code == 200
    published = store.list_published()[0]
    assert client.get(f"/entry/{published['id']}").status_code == 200


def test_sme_approval_writes_manual_audit_row():
    _reset()
    _load_demo()
    before = store.counts()["published"]
    pending = store.list_pending()[0]
    ingestion.approve_review(pending["id"], "edited problem",
                             "edited resolution", "CI SME")
    assert store.counts()["published"] == before + 1
    rows = audit.read_audit()
    # Both validation kinds should be present: auto (from the 5 IT publishes)
    # and manual (from the approval we just did).
    assert any(r["Validation Process"] == "manual" for r in rows)
    assert any(r["Validation Process"] == "auto" for r in rows)
