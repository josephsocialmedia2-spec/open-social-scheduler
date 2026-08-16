#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / 'publisher' / 'clients'


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', required=True, help='ISO week, e.g. 2026-W34')
    parser.add_argument('--action', choices=['approve','revoke'], default='approve')
    parser.add_argument('--client', action='append', default=[], help='optional client id; repeatable')
    args = parser.parse_args()

    changed = 0
    selected = set(args.client)
    for client_path in sorted(CLIENT_DIR.glob('*.json')):
        if client_path.name.startswith('_'):
            continue
        client = load(client_path)
        if not client.get('active', False):
            continue
        client_id = str(client.get('id') or '')
        if selected and client_id not in selected:
            continue
        approval = client.get('approval', {})
        if not approval.get('required', False):
            continue
        rel = str(approval.get('file') or '').strip()
        if not rel:
            continue
        path = ROOT / rel
        state = load(path) if path.exists() else {'client_id': client_id, 'mode': 'iso_week', 'approved': [], 'revoked': []}
        approved = [str(x) for x in state.get('approved', [])]
        revoked = [str(x) for x in state.get('revoked', [])]
        before = json.dumps(state, sort_keys=True)
        if args.action == 'approve':
            if args.key not in approved:
                approved.append(args.key)
            revoked = [x for x in revoked if x != args.key]
        else:
            approved = [x for x in approved if x != args.key]
            if args.key not in revoked:
                revoked.append(args.key)
        state['approved'] = sorted(set(approved))
        state['revoked'] = sorted(set(revoked))
        if json.dumps(state, sort_keys=True) != before:
            save(path, state)
            changed += 1
            print(f"{args.action}: {client_id} {args.key}")
    print(f"Changed {changed} approval file(s).")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
