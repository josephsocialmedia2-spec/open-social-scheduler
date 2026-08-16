#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIR = ROOT / 'publisher' / 'clients'
QUEUE_PATH = ROOT / 'publisher' / 'queue.json'


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
    affected_clients: set[str] = set()

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

        affected_clients.add(client_id)
        path = ROOT / rel
        state = load(path) if path.exists() else {
            'client_id': client_id,
            'mode': 'iso_week',
            'approved': [],
            'revoked': [],
        }
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

    queue_changed = 0
    if QUEUE_PATH.exists() and affected_clients:
        queue = load(QUEUE_PATH)
        for job in queue.get('jobs', []):
            if str(job.get('client_id') or '') not in affected_clients:
                continue
            if str(job.get('approval_key') or '') != args.key:
                continue
            if job.get('status') in {'published', 'disabled'}:
                continue

            if args.action == 'approve':
                # The weekly renderer stores media as a GitHub Actions artifact rather
                # than committing binaries to the repository. At approval time the
                # queue therefore trusts the already-rendered media references; the
                # direct publisher validates the downloaded files again before upload.
                if job.get('status') != 'partially_published':
                    job['status'] = 'ready'
                job.pop('blocked_reason', None)
            else:
                job['status'] = 'awaiting_approval'
                job['blocked_reason'] = f"approval required for {args.key}"
            queue_changed += 1

        if queue_changed:
            save(QUEUE_PATH, queue)

    print(f"Changed {changed} approval file(s); updated {queue_changed} queue job(s).")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
