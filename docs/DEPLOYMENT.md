# Deployment

## Prerequisites

- Python 3.9+
- SQLite (built-in)
- Network access for notification channels

## Install

```bash
git clone https://github.com/tylerdotai/permission-vending-machine.git
cd permission-vending-machine
pip install -e .
```

## Configuration

```bash
cp config.example.yaml config.yaml
$EDITOR config.yaml
```

Set credentials via environment variables or directly in `config.yaml`:

```bash
export SENDBLUE_API_KEY="your-key"
export SMTP_USER="user"
export SMTP_PASSWORD="pass"
export DISCORD_WEBHOOK_URL="https://..."
```

## Directory Layout

```
.
├── config.yaml          # Your config (not committed)
├── grants.db            # SQLite database (auto-created)
├── safe-rm              # Wrappers (add to PATH)
├── safe-git-push
├── safe-trash
└── src/pvm/             # Python package
```

## Adding Wrappers to PATH

```bash
export PATH="$PATH:~/flume/permission-vending-machine/wrappers"
# Or symlink:
ln -s ~/flume/permission-vending-machine/wrappers/safe-rm /usr/local/bin/safe-rm
ln -s ~/flume/permission-vending-machine/wrappers/safe-git-push /usr/local/bin/safe-git-push
ln -s ~/flume/permission-vending-machine/wrappers/safe-trash /usr/local/bin/safe-trash
```

## Database Location

Default: `./grants.db` (relative to working directory).

Set via:
- `config.yaml`: `vault.db_path`
- Env var: `PVM_DB`
- Constructor: `Vault("/path/to/grants.db")`

## Running as a Service

PVM itself is stateless (request-response). For blocking `pvm request --block` calls, run the poller in a long-lived process:

```bash
# Long-running approver process
pvm request --scope "/tmp/build" --reason "cleaning" --duration 10 --block --timeout 600
```

For callback-based (non-blocking), expose the callback endpoint:

```python
from pvm.vault import Vault
from pvm.approval import CallbackHandler

vault = Vault()
handler = CallbackHandler(vault)

# Flask/FastAPI
@app.post("/pvm/approve")
def approve():
    ok = handler.handle_approval(request.json())
    return {"ok": ok}
```

## Backup

The SQLite database is the source of truth. Back it up regularly:

```bash
cp grants.db "grants.db.$(date +%Y%m%d)"
```

## Upgrading

```bash
git pull
pip install -e .
# DB schema is auto-migrated on startup
```
