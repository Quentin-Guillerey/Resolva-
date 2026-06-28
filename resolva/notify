"""
SME notification.

This is the toolkit's Slack alerting, repurposed: instead of pinging on every
query, Resolva pings the relevant department's SME when a resolution lands in
the review queue and needs a human decision. Optional — silent no-op if no
webhook is configured.

Auto-routing to Asana/Zapier for approved follow-ups stays on the roadmap, as
in the toolkit; this is the notification half only.
"""

import requests


def notify_sme(cfg: dict, *, ticket_number, department, sensitivity, reason):
    webhook = cfg.get("SLACK_WEBHOOK_URL", "")
    if not webhook:
        return
    flag = " [LEGAL — MANDATORY REVIEW]" if sensitivity == "legal" else ""
    payload = {
        "text": (f"*Resolva — SME review needed{flag}*\n"
                 f"Ticket: {ticket_number}\n"
                 f"Department: {department}\n"
                 f"Sensitivity: {sensitivity}\n"
                 f"Reason: {reason}"),
        "username": "Resolva",
        "icon_emoji": ":mag:",
    }
    try:
        requests.post(webhook, json=payload, timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"[notify] Slack send failed: {e}")
