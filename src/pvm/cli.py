"""PVM CLI entry point — pvm command."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .models import Decision
from .notifier import Notifier
from .vault import Vault

DEFAULT_CONFIG = os.environ.get("PVM_CONFIG", "./config.yaml")


def _vault(cfg: str) -> Vault:
    import yaml
    path = Path(cfg)
    if path.exists():
        raw = yaml.safe_load(path.read_text())
        db_path = raw.get("vault", {}).get("db_path", "./grants.db")
    else:
        db_path = "./grants.db"
    return Vault(db_path)


def cmd_request(args: argparse.Namespace) -> int:
    vault = _vault(args.config)
    notifier = Notifier(args.config)

    from .models import PermissionRequest
    from .approval.polling import ApprovalPoller

    request = PermissionRequest.create(
        agent_id=args.agent_id or os.environ.get("AGENT_ID", "default"),
        operation=args.operation or "unknown",
        scope=args.scope,
        scope_type=args.scope_type or "path",
        reason=args.reason or "",
        ttl_minutes=min(args.duration or notifier.default_ttl_minutes(),
                        notifier.max_ttl_minutes()),
    )

    vault.log_audit(
        entry_type=__import__("pvm.models", fromlist=["AuditEntryType"]).AuditEntryType.REQUEST,
        agent_id=request.agent_id,
        scope=request.scope,
        decision=Decision.DENIED,
        details=f"Permission request created: {request.request_id} for {request.scope}",
    )

    print(f"Requesting approval for: {request.scope}")
    print(f"Token: {request.approval_token}")
    print(f"Duration: {request.ttl_minutes}min")
    print(f"Notifying: {', '.join(notifier.enabled_channels)}...")

    results = notifier.notify_approvers(
        message=args.reason or "Please approve this operation.",
        approval_token=request.approval_token,
        agent_id=request.agent_id,
        scope=request.scope,
        reason=request.reason,
        ttl_minutes=request.ttl_minutes,
    )

    for ch, result in results.items():
        status = "✅" if result.success else f"❌ {result.error}"
        print(f"  {ch}: {status}")

    # Wait for approval if blocking
    if args.block:
        print(f"\nWaiting up to {args.timeout}s for approval...")
        poller = ApprovalPoller(vault)

        def on_approve(req):
            print(f"\n✅ Request approved! Grant ready.")

        grant = poller.wait_for_decision(
            request=request,
            timeout_seconds=args.timeout,
            on_approve=on_approve,
        )
        if grant:
            print(f"✅ Approved! Grant: {grant.grant_id}")
        else:
            print("⏰ Timed out — no approval received.")
            return 1
    else:
        print("\nNot blocking. Approve via any configured channel, then run your command.")
        print(f"Approval token: {request.approval_token}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    vault = _vault(args.config)
    grants = vault.get_active_grants(agent_id=args.agent_id)

    if not grants:
        print("No active grants found.")
        return 0

    print(f"Active grants for {args.agent_id or 'all agents'}:\n")
    for g in grants:
        remaining = g.remaining_minutes()
        print(f"  {g.grant_id}")
        print(f"    scope:    {g.scope}")
        print(f"    reason:   {g.reason}")
        print(f"    expires:  in {remaining:.1f} min")
        print(f"    by:       {g.approved_by or 'N/A'}")
        print()
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    vault = _vault(args.config)
    grant = vault.get_grant(args.grant_id)
    if not grant:
        print(f"Grant not found: {args.grant_id}")
        return 1
    vault.revoke_grant(args.grant_id)
    print(f"Revoked: {args.grant_id} ({grant.scope})")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    vault = _vault(args.config)
    decision = Decision(args.decision) if args.decision else None
    entries = vault.get_audit_log(
        agent_id=args.agent_id,
        decision=decision,
        limit=args.limit,
    )

    if not entries:
        print("No audit entries found.")
        return 0

    print(f"Audit log (last {len(entries)} entries):\n")
    for e in entries:
        decision_str = f"[{e.decision.value}]" if e.decision else ""
        print(f"  {e.timestamp.strftime('%Y-%m-%d %H:%M:%S')} {decision_str}")
        print(f"    {e.details}")
        print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    vault = _vault(args.config)
    scope_type = args.scope_type or "path"
    if scope_type == "path":
        ok = vault.check_grant_glob(args.agent_id or "default", args.scope, scope_type)
    else:
        ok = vault.check_grant(args.agent_id or "default", args.scope)
    if ok:
        print(f"GRANTED: {args.scope}")
        return 0
    print(f"DENIED:  {args.scope}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="pvm", description="Permission Vending Machine")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Config file path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # pvm request
    r = sub.add_parser("request", help="Request a permission grant")
    r.add_argument("--scope", required=True, help="Scope to request (e.g. path or repo URL)")
    r.add_argument("--scope-type", default="path", choices=["path", "repo"], help="Scope type")
    r.add_argument("--reason", default="", help="Reason for the request")
    r.add_argument("--duration", type=int, help="Duration in minutes")
    r.add_argument("--agent-id", help="Agent ID (default: from AGENT_ID env)")
    r.add_argument("--operation", help="Operation name")
    r.add_argument("--block", action="store_true", help="Block until approved or timeout")
    r.add_argument("--timeout", type=int, default=300, help="Timeout for --block (seconds)")
    r.set_defaults(func=cmd_request)

    # pvm status
    s = sub.add_parser("status", help="List active grants")
    s.add_argument("--agent-id", help="Filter by agent ID")
    s.set_defaults(func=cmd_status)

    # pvm revoke
    rv = sub.add_parser("revoke", help="Revoke a grant")
    rv.add_argument("--grant-id", dest="grant_id", required=True)
    rv.set_defaults(func=cmd_revoke)

    # pvm log
    l = sub.add_parser("log", help="Show audit log")
    l.add_argument("--agent-id", dest="agent_id", help="Filter by agent ID")
    l.add_argument("--decision", choices=[d.value for d in Decision], help="Filter by decision")
    l.add_argument("--limit", type=int, default=100)
    l.set_defaults(func=cmd_log)

    # pvm check
    c = sub.add_parser("check", help="Check if a grant exists for scope")
    c.add_argument("--scope", required=True)
    c.add_argument("--agent-id", dest="agent_id", default="default")
    c.add_argument("--scope-type", default="path", choices=["path", "repo"])
    c.set_defaults(func=cmd_check)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
