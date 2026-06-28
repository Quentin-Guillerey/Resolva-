#!/usr/bin/env python3
"""
Resolva — Flask web app (prototype / portfolio demo).

Run locally:
    pip install -r requirements.txt
    python app.py
    # then open http://127.0.0.1:5000

Same codebase is packaged as a desktop .exe via resolva.spec (see README).
The web version is for multi-department simultaneous access in a demo; the
packaged version launches this same app in the default browser.

Prototype honesty: there is no real authentication here. The SME identity on
the review screen is typed in, not verified. Real per-department SME accounts
and SSO are roadmap, not built.
"""

import csv
import io
import os
import sys

from flask import (Flask, render_template, request, redirect, url_for, flash)

from resolva import config, store
from resolva.ingestion import ingest_ticket, approve_review, reject_review
from resolva.audit import read_audit


def resource_path(rel: str) -> str:
    """Locate bundled files in both dev and PyInstaller (--onefile) runs."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = "resolva-prototype-secret"  # demo only

store.init_db()


@app.context_processor
def inject_counts():
    return {"counts": store.counts()}


@app.route("/")
def dashboard():
    dept = request.args.get("department", "All")
    query = request.args.get("q", "").strip()
    entries = store.list_published(department=dept, query=query)
    departments = ["All"] + store.list_departments()
    return render_template("dashboard.html", entries=entries,
                           departments=departments, current_dept=dept, query=query)


@app.route("/entry/<int:entry_id>")
def entry_detail(entry_id):
    e = store.get_entry(entry_id)
    if not e:
        flash("Entry not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("entry.html", e=e)


@app.route("/ingest", methods=["GET", "POST"])
def ingest():
    if request.method == "POST":
        cfg = config.load()
        results = []

        file = request.files.get("csvfile")
        if file and file.filename:
            text = file.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                row["it_closed_no_followup"] = str(
                    row.get("it_closed_no_followup", "")
                ).strip().lower() in ("yes", "true", "1")
                results.append(ingest_ticket(row, cfg))
        elif request.form.get("description"):
            ticket = {
                "ticket_number": request.form.get("ticket_number", ""),
                "client_id": request.form.get("client_id", ""),
                "description": request.form.get("description", ""),
                "resolution": request.form.get("resolution", ""),
                "time_to_resolve": request.form.get("time_to_resolve", ""),
                "stakeholders": request.form.get("stakeholders", ""),
                "it_closed_no_followup": bool(request.form.get("it_closed_no_followup")),
            }
            results.append(ingest_ticket(ticket, cfg))
        else:
            flash("Upload a CSV or fill in the single-ticket form.", "error")
            return redirect(url_for("ingest"))

        auto = sum(1 for r in results if r["route"] == "auto")
        manual = len(results) - auto
        flash(f"Ingested {len(results)} ticket(s): {auto} auto-published, "
              f"{manual} sent to SME review.", "success")
        return render_template("ingest.html", results=results, ai_on=config.ai_enabled(cfg))

    return render_template("ingest.html", results=None, ai_on=config.ai_enabled(config.load()))


@app.route("/load-demo", methods=["POST"])
def load_demo():
    cfg = config.load()
    path = resource_path(os.path.join("data", "demo_tickets.csv"))
    n = 0
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            row["it_closed_no_followup"] = str(
                row.get("it_closed_no_followup", "")
            ).strip().lower() in ("yes", "true", "1")
            ingest_ticket(row, cfg)
            n += 1
    flash(f"Loaded {n} sanitized demo tickets.", "success")
    return redirect(url_for("dashboard"))


@app.route("/review")
def review_queue():
    return render_template("review.html", entries=store.list_pending())


@app.route("/review/<int:entry_id>", methods=["GET", "POST"])
def review_detail(entry_id):
    e = store.get_entry(entry_id)
    if not e:
        flash("Entry not found.", "error")
        return redirect(url_for("review_queue"))

    if request.method == "POST":
        reviewer = request.form.get("reviewed_by", "").strip()
        if not reviewer:
            flash("Enter your name as the reviewing SME before deciding.", "error")
            return render_template("review_detail.html", e=e)
        if request.form.get("action") == "approve":
            approve_review(entry_id,
                           request.form.get("summary_problem", "").strip(),
                           request.form.get("summary_resolution", "").strip(),
                           reviewer)
            flash(f"Entry approved and published by {reviewer}.", "success")
        else:
            reject_review(entry_id, reviewer)
            flash(f"Entry rejected by {reviewer}.", "success")
        return redirect(url_for("review_queue"))

    return render_template("review_detail.html", e=e)


@app.route("/audit")
def audit_view():
    return render_template("audit.html", rows=read_audit())


@app.route("/settings", methods=["GET", "POST"])
def settings():
    cfg = config.load()
    if request.method == "POST":
        cfg["ANTHROPIC_API_KEY"] = request.form.get("ANTHROPIC_API_KEY", "").strip()
        cfg["ANTHROPIC_MODEL"] = request.form.get("ANTHROPIC_MODEL", "").strip() or "claude-sonnet-4-6"
        cfg["SLACK_WEBHOOK_URL"] = request.form.get("SLACK_WEBHOOK_URL", "").strip()
        config.save(cfg)
        flash("Settings saved (stored on this computer only).", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", cfg=cfg,
                           ai_on=config.ai_enabled(cfg),
                           slack_on=config.slack_enabled(cfg))


def main():
    # debug=False so the packaged .exe doesn't try to spawn a reloader.
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
