# Notification Channels

PVM supports 5 notification channels simultaneously. Enable as many as you need.

## Sendblue (iMessage / SMS)

Best for personal approval workflows. Sends to phone numbers via iMessage or SMS.

**Setup:**
1. Get API key from [sendblue.co](https://sendblue.co)
2. Set `SENDBLUE_API_KEY` env var
3. Configure `from_number` (your Sendblue number) and `approver_numbers`

**Approval flow:**
Reply to the iMessage/SMS with `APPROVE` or `DENY` (partial keyword matching supported).

## Email (SMTP)

Standard email with HTML multipart support.

**Setup:**
1. For iCloud: App password from appleid.apple.com
2. Set `SMTP_USER`, `SMTP_PASSWORD`
3. Configure `approver_emails`

**Approval flow:**
Reply to the email with `APPROVE` or `DENY` in the subject or body.

## Discord

Webhook-based. Fast, good for team environments.

**Setup:**
1. Server Settings → Integrations → Webhooks → New Webhook
2. Copy webhook URL → `DISCORD_WEBHOOK_URL`
3. Approvers react with ✅ or ❌ to the approval message

**Approval flow:**
React to the Discord embed with ✅ (approve) or ❌ (deny). The message includes an inline keyboard with Approve/Deny buttons.

## Telegram

Bot API with inline keyboard buttons.

**Setup:**
1. BotFather → `/newbot` → copy token → `TELEGRAM_BOT_TOKEN`
2. Start a chat with your bot
3. Add your chat ID to `approver_chat_ids` (use [@userinfobot](https://t.me/userinfobot) to find it)

**Approval flow:**
Tap the inline "Approve" or "Deny" button on the bot message.

## Slack

Webhook with Block Kit interactive buttons.

**Setup:**
1. api.slack.com → Your Apps → Incoming Webhooks
2. Create webhook → copy URL → `SLACK_WEBHOOK_URL`
3. Enable interactivity on your app

**Approval flow:**
Click the "Approve" or "Deny" button in the Slack message.

## Callback Endpoints

For programmatic integrations, use the callback handler directly:

```python
from pvm.vault import Vault
from pvm.approval import CallbackHandler

vault = Vault()
handler = CallbackHandler(vault)

# POST /approve
payload = {
    "approval_token": "tok_abc123",
    "agent_id": "coder",
    "scope": "/tmp/build",
    "scope_type": "path",
    "reason": "cleanup",
    "ttl_minutes": 5,
}
handler.handle_approval(payload)
```
