# Permission Vending Machine (PVM)

<a href="https://pypi.python.org/pypi/pvm/"><img src="https://img.shields.io/pypi/v/pvm.svg" alt="pypi"></a>
<a href="https://github.com/tylerdotai/permission-vending-machine/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/pvm.svg" alt="license"></a>
<a href="https://github.com/tylerdotai/permission-vending-machine/actions"><img src="https://img.shields.io/github/actions/status/tylerdotai/permission-vending-machine/main.svg" alt="build"></a>
<a href="https://pypi.python.org/pypi/pvm/"><img src="https://img.shields.io/pypi/pyversions/pvm.svg" alt="python"></a>

**Local multi-channel approval system for AI agent permissions.** PVM gates sensitive operations (file deletion, force-push, trash) behind a human approver — notified via iMessage/SMS, Email, Discord, Telegram, or Slack.

---

## Overview

When an AI agent wants to run a guarded operation, it must request a time-limited grant from a human approver. PVM sends the request to every configured notification channel simultaneously, logs every decision, and enforces grants before running dangerous commands.

```
Agent                    PVM                       Approver
  |                        |                          |
  |--- request(scope) --->|                          |
  |                        |--- notify all channels ->|
  |                        |                          |
  |                        |<-- approve/deny --------|
  |                        |                          |
  |<-- grant or deny -----|                          |
  |                        |                          |
  |--- check_grant() ---->|                           |
  |<-- GRANTED ------------|                          |
  |                        |                          |
  |--- execute ------------|------------------------->|
```

## Features

- **SQLite grant registry** — durable, queryable, with TTL and revocation
- **Audit log** — every DENIED/GRANTED/EXPIRED/REVOKED event captured
- **5 notification channels** — Sendblue (iMessage/SMS), SMTP Email, Discord, Telegram, Slack
- **Safe wrappers** — drop-in replacements for `rm`, `git push --force`, `trash` that check grants first
- **Polling + callbacks** — poll approval sources or handle incoming webhook callbacks
- **OpenClaw skill** — `pvm_request`, `pvm_status`, `pvm_revoke` tools for agent integration

---

## Install

```bash
# Clone
git clone https://github.com/tylerdotai/permission-vending-machine.git
cd permission-vending-machine

# Install
pip install -e .

# Or with poetry
poetry install
```

## Quick Start

```bash
# 1. Copy and edit config
cp config.example.yaml config.yaml
$EDITOR config.yaml   # fill in API keys and approver contacts

# 2. Request a grant
pvm request scope="delete:/Users/soup/flume/data/backups" \
           reason="cleaning old backups" \
           duration=5

# 3. Approve via any channel (iMessage reply, Discord reaction, email link, etc.)

# 4. Run the guarded command
safe-rm -rf /Users/soup/flume/data/backups
# → grant found, executes normally

# 5. Check active grants
pvm status agent_id="coder"

# 6. Revoke early
pvm revoke grant_id="grant_abc123"
```

---

## Configuration

All config via `config.yaml`. Environment variables supported with `${VAR}` syntax.

| Section | Key | Description |
|---------|-----|-------------|
| `vault.db_path` | path | SQLite database path (default: `./grants.db`) |
| `vault.default_ttl_minutes` | int | Default grant TTL (default: 30) |
| `vault.max_ttl_minutes` | int | Maximum allowed TTL (default: 480 = 8h) |
| `channels.sendblue.*` | | Sendblue iMessage/SMS |
| `channels.email.*` | | SMTP email |
| `channels.discord.*` | | Discord webhook |
| `channels.telegram.*` | | Telegram bot API |
| `channels.slack.*` | | Slack webhook |
| `permissions.guarded_operations` | list | Operations requiring approval |
| `agent_workspaces` | dict | Per-agent workspace root paths |

Full example: [`config.example.yaml`](config.example.yaml)

---

## CLI Commands

```bash
pvm request scope=<scope> reason=<reason> duration=<minutes>
pvm status [agent_id=<id>]
pvm revoke grant_id=<id>
pvm log [--agent <id>] [--decision <decision>] [--limit <n>]
```

---

## Wrappers

Prepend `safe-` to guarded commands. Each wrapper:
1. Checks vault for an active grant matching the scope
2. If no grant → logs DENIED, exits 1, prints how to request one
3. If grant found → executes the real command, logs SUCCESS

| Wrapper | Guards | Scope format |
|---------|--------|-------------|
| `safe-rm` | `rm` | path prefix match |
| `safe-git-push` | `git push --force` | repo URL or path |
| `safe-trash` | `trash` | path prefix match |

---

## Architecture

```
permission-vending-machine/
├── README.md
├── LICENSE
├── pyproject.toml
├── config.example.yaml
├── src/
│   ├── __init__.py
│   ├── vault.py          # SQLite grant registry + audit log
│   ├── models.py         # Grant, PermissionRequest, AuditEntry dataclasses
│   ├── notifier.py       # Multicast dispatcher
│   └── channels/
│       ├── base.py       # Abstract NotificationChannel
│       ├── sendblue.py   # Sendblue API (iMessage/SMS)
│       ├── email.py      # SMTP email
│       ├── discord.py    # Discord webhook
│       ├── telegram.py   # Telegram bot API
│       └── slack.py      # Slack webhook
├── approval/
│   ├── polling.py        # Poll approval sources
│   └── callback.py       # Handle incoming approval callbacks
├── wrappers/
│   ├── safe-rm
│   ├── safe-git-push
│   └── safe-trash
├── skills/
│   └── permission-guard/
│       └── SKILL.md      # OpenClaw skill for agent integration
├── tests/
│   ├── test_vault.py
│   ├── test_notifier.py
│   └── test_wrappers.py
└── docs/
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── CHANNELS.md
```

### Text Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Agent Process                            │
│  ┌──────────┐    ┌────────────────┐    ┌───────────────────┐  │
│  │ safe-rm  │───>│  vault.py       │───>│  grants.db         │  │
│  │ safe-push│    │  check_grant()  │    │  (SQLite)          │  │
│  │ safe-trash│   │  create_grant() │    │                    │  │
│  └──────────┘    │  log_audit()    │    └───────────────────┘  │
│       │         └───────┬──────────┘                            │
│       │                  │                                       │
│       ▼                  ▼                                       │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    notifier.py                          │     │
│  │              notify_approvers(message)                  │     │
│  └───────┬─────────┬─────────┬─────────┬──────────────────┘     │
│          │         │         │         │                        │
│          ▼         ▼         ▼         ▼                        │
│    ┌─────────┐ ┌───────┐ ┌─────────┐ ┌─────────┐                │
│    │Sendblue │ │ Email │ │ Discord │ │ Telegram│                │
│    │(iMessage│ │ (SMTP)│ │webhook  │ │  bot    │                │
│    │ /SMS)   │ └───────┘ └─────────┘ └─────────┘                │
│    └─────────┘                              ┌─────────┐          │
│                                              │ Slack   │          │
│                                              └─────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Approver       │
                    │ (human reviews  │
                    │  notification,  │
                    │  approves via   │
                    │  reply/channel) │
                    └─────────────────┘
```

---

## Testing

```bash
pytest tests/ -v
```

---

## License

MIT — see [LICENSE](LICENSE)
