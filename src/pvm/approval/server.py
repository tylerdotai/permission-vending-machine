"""
Approval HTTP server — Flask app for handling Discord/email approval callbacks.

Run as: pvm serve [--port 8080]

Sets up two endpoints:
  GET  /                 — Approval status dashboard
  POST /approve/<token>  — Approve a request by token
  POST /deny/<token>     — Deny a request by token

The PVM Discord notification embeds include links to these endpoints so Tyler
can approve/deny by clicking links in the notification.
"""

from __future__ import annotations

import argparse
import logging
from typing import Callable, Optional

from flask import Flask, jsonify, request as flask_request

logger = logging.getLogger(__name__)


def create_app(
    on_approve: Callable[[str, str], None],  # (token, approver)
    on_deny: Callable[[str, str], None],      # (token, approver)
    approver_name: str = "Tyler",
) -> Flask:
    """
    Build the Flask approval server.

    `on_approve(token, approver)` is called when /approve/<token> is hit.
    `on_deny(token, approver)` is called when /deny/<token> is hit.
    """
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    _on_approve = on_approve
    _on_deny = on_deny
    _approver = approver_name

    @app.route("/")
    def index():
        return {
            "service": "PVM Approval Server",
            "status": "running",
            "endpoints": {
                "GET /": "This page",
                "POST /approve/<token>": "Approve a pending request",
                "POST /deny/<token>": "Deny a pending request",
                "GET /pending": "List pending requests (from vault)",
            },
        }

    @app.route("/approve/<token>", methods=["GET", "POST"])
    def approve(token: str):
        logger.info("APPROVE received via HTTP: token=%s", token)
        try:
            _on_approve(token, _approver)
            return jsonify({"status": "approved", "token": token})
        except Exception as exc:
            logger.exception("Approve failed for token %s", token)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/deny/<token>", methods=["GET", "POST"])
    def deny(token: str):
        logger.info("DENY received via HTTP: token=%s", token)
        try:
            _on_deny(token, _approver)
            return jsonify({"status": "denied", "token": token})
        except Exception as exc:
            logger.exception("Deny failed for token %s", token)
            return jsonify({"status": "error", "message": str(exc)}), 500

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def run_server(
    on_approve: Callable[[str, str], None],
    on_deny: Callable[[str, str], None],
    host: str = "0.0.0.0",
    port: int = 8080,
    approver_name: str = "Tyler",
    debug: bool = False,
) -> None:
    """Run the approval server. Blocks indefinitely."""
    app = create_app(on_approve=on_approve, on_deny=on_deny, approver_name=approver_name)
    # Bind to all interfaces so Tyler can hit it from his phone on LAN
    app.run(host=host, port=port, debug=debug)
