"""Sendblue (iMessage/SMS) notification channel."""

import logging
from typing import Optional

import requests

from .base import NotificationChannel, NotificationResult

logger = logging.getLogger(__name__)

SEND_URL = "https://api.sendblue.co/api/send-sms"


class SendblueChannel(NotificationChannel):
    name = "sendblue"

    def __init__(
        self,
        api_key: str,
        from_number: str,
        approver_numbers: list[str],
    ):
        self.api_key = api_key
        self.from_number = from_number
        self.approver_numbers = approver_numbers

    def send(
        self,
        message: str,
        approval_token: str,
        *,
        agent_id: Optional[str] = None,
        scope: Optional[str] = None,
        reason: Optional[str] = None,
        ttl_minutes: Optional[int] = None,
        approver_name: Optional[str] = None,
    ) -> NotificationResult:
        full_message = self._format_message(
            message,
            agent_id=agent_id,
            scope=scope,
            reason=reason,
            ttl_minutes=ttl_minutes,
        )
        errors = []
        for number in self.approver_numbers:
            try:
                resp = requests.post(
                    SEND_URL,
                    json={
                        "api_key": self.api_key,
                        "from_number": self.from_number,
                        "to_number": number,
                        "message": full_message,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=15,
                )
                data = resp.json()
                if resp.status_code != 200 or data.get("status") != "success":
                    errors.append(f"{number}: {data}")
            except Exception as exc:
                errors.append(f"{number}: {exc}")

        if errors:
            return NotificationResult(
                channel=self.name,
                success=False,
                message=full_message,
                error="; ".join(errors),
            )
        return NotificationResult(
            channel=self.name,
            success=True,
            message=full_message,
        )
