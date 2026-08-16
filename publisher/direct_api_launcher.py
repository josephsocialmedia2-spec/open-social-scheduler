#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'publisher' / 'queue.json'
CLIENTS = ROOT / 'publisher' / 'clients'

SECRET_NAMES = [
    'FACEBOOK_PAGE_ACCESS_TOKEN',
    'INSTAGRAM_ACCESS_TOKEN',
    'INSTAGRAM_USER_ID',
    'TIKTOK_ACCESS_TOKEN',
    'LINKEDIN_ACCESS_TOKEN',
    'LINKEDIN_AUTHOR_URN',
    'YOUTUBE_CLIENT_ID',
    'YOUTUBE_CLIENT_SECRET',
    'YOUTUBE_REFRESH_TOKEN',
    'PINTEREST_ACCESS_TOKEN',
    'PINTEREST_BOARD_ID',
]


def arg_value(name: str) -> str:
    try:
        idx = sys.argv.index(name)
        return sys.argv[idx + 1]
    except (ValueError, IndexError):
        return ''


def main() -> int:
    job_id = arg_value('--job-id')
    if not job_id:
        raise SystemExit('--job-id is required')
    queue = json.loads(QUEUE.read_text(encoding='utf-8'))
    job = next((j for j in queue.get('jobs', []) if j.get('id') == job_id), None)
    if not job:
        raise SystemExit(f'job not found: {job_id}')
    client_path = CLIENTS / f"{job['client_id']}.json"
    client = json.loads(client_path.read_text(encoding='utf-8'))
    prefix = str(client.get('publishing', {}).get('secret_prefix') or '').strip().upper()
    if prefix:
        for name in SECRET_NAMES:
            value = os.getenv(f'{prefix}_{name}', '').strip()
            if value:
                os.environ[name] = value

    import direct_api_publish as publisher
    publisher.PUBLISHERS['linkedin-page'] = publisher.linkedin_text
    publisher.REQUIRED_ENV['linkedin-page'] = publisher.REQUIRED_ENV['linkedin']
    return publisher.main()


if __name__ == '__main__':
    raise SystemExit(main())
