from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS_PATH = ROOT / "growth" / "groups.json"

VALID_COMMANDS = {"approve": "APPROVED", "joined": "JOIN_REQUESTED", "member": "MEMBER", "pause": "PAUSED", "reject": "REJECTED"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    command = os.environ.get("APPROVAL_COMMAND", "").strip()
    if not command.startswith("/"):
        print("No command")
        return 0
    match = re.match(r"^/(approve|joined|member|pause|reject)\s+(.+)$", command, re.I)
    if not match:
        print("Unsupported command")
        return 0
    action = match.group(1).lower()
    selection = match.group(2).strip()
    target_status = VALID_COMMANDS[action]
    data = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    groups = data.get("groups", [])
    if selection.lower() == "all":
        batch_id = os.environ.get("APPROVAL_BATCH_ID", "").strip()
        selected = {g["id"] for g in groups if g.get("batch_id") == batch_id and g.get("status") == "PENDING_APPROVAL"}
    else:
        selected = {x.upper() for x in re.findall(r"FBG-[A-F0-9]{10}", selection, re.I)}
    changed = 0
    for group in groups:
        if group.get("id", "").upper() not in selected:
            continue
        group["status"] = target_status
        stamp = now_iso()
        if target_status == "APPROVED":
            group["approved_at"] = stamp
        elif target_status == "JOIN_REQUESTED":
            group["join_requested_at"] = stamp
        elif target_status == "MEMBER":
            group["member_at"] = stamp
        changed += 1
    if changed:
        data["updated_at"] = now_iso()
        GROUPS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"action": action, "status": target_status, "changed": changed}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
