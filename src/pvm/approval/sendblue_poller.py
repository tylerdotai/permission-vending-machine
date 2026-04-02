"""Sendblue inbound polling — detect approval/denial replies via iMessage/SMS."""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Pattern to extract approval token from message body
TOKEN_RE = re.compile(r"(?:approval\s+)?token:\s*([a-zA-Z0-9_-]+)", re.IGNORECASE)


@dataclass
class SendblueApproval:
    approval_token: str
    decision: str  # "APPROVE" or "DENY"
    from_number: str


class SendbluePoller:
    """
    Poll Sendblue iMessage inbox for approval responses.

    Uses `sendblue messages --inbound` to check for incoming messages
    containing APPROVE or DENY and an approval token.

    Usage::

        def on_approval(token: str, decision: str, from_number: str):
            if decision == "APPROVE":
                vault.create_grant(...)

        poller = SendbluePoller()
        poller.poll(on_approval=on_approval, interval_seconds=15)
    """

    def __init__(self):
        pass

    def poll(
        self,
        on_approval: Callable[[str, str, str], None],
        interval_seconds: int = 15,
    ) -> None:
        """
        Run the Sendblue polling loop indefinitely.

        `on_approval` is called with (approval_token, decision, from_number).
        """
        while True:
            try:
                self._poll_once(on_approval)
            except Exception:
                logger.exception("Sendblue poll error")
            time.sleep(interval_seconds)

    def _poll_once(
        self,
        on_approval: Callable[[str, str, str], None],
    ) -> list[SendblueApproval]:
        """Check for new inbound messages with approval/denial."""
        approvals = []

        try:
            result = subprocess.run(
                ["sendblue", "messages", "--limit", "20", "--inbound"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning("sendblue messages failed: %s", result.stderr.strip())
                return []
        except Exception as exc:
            logger.warning("sendblue CLI error: %s", exc)
            return []

        lines = result.stdout.strip().splitlines()
        for approval in self._parse_output(lines):
            logger.info(
                "Sendblue approval detected: token=%s decision=%s from=%s",
                approval.approval_token,
                approval.decision,
                approval.from_number,
            )
            on_approval(approval.approval_token, approval.decision, approval.from_number)
            approvals.append(approval)

        return approvals

    def _parse_output(self, lines: list[str]) -> list[SendblueApproval]:
        """
        Parse sendblue output for approval messages.

        Expected format:
           IN Mar 26, 10:01 PM  +1 (945) 269-2639 [RECEIVED]
             APPROVE tok_abc123

        Also handles bare "APPROVE" or "DENY" (no token) — caller will
        resolve to the most recent pending request.
        """
        approvals = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("IN ") and "[RECEIVED]" in line:
                # Extract full phone number with regex — handles split tokens
                # Format: "IN Apr 2, 4:58 PM  +1 (945) 269-2639 [RECEIVED]"
                phone_match = re.search(r"\+?\d[\d\s\-\(\)]+?\d(?=\s*\[)", line)
                if phone_match:
                    from_number = phone_match.group(0).strip()
                else:
                    from_number = ""
                body_lines = []
                i += 1
                while i < len(lines) and lines[i] and lines[i][0] in " \t":
                    body_lines.append(lines[i].strip())
                    i += 1
                body = " ".join(body_lines).upper()

                decision = None
                if "APPROVE" in body and "DENY" not in body:
                    decision = "APPROVE"
                elif "DENY" in body:
                    decision = "DENY"
                else:
                    continue

                # Try to extract token; if not found, leave token empty
                # (caller will resolve to most recent pending request)
                token_match = TOKEN_RE.search(body)
                approval_token = token_match.group(1) if token_match else ""

                approvals.append(SendblueApproval(
                    approval_token=approval_token,
                    decision=decision,
                    from_number=from_number,
                ))
            else:
                i += 1

        return approvals
