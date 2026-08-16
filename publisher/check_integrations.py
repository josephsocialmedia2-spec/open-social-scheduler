#!/usr/bin/env python3
from __future__ import annotations
import json, os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def norm_url(v: str) -> str:
    return (v or '').strip().rstrip('/')


def handle_from_url(url: str) -> str:
    url = norm_url(url)
    if not url:
        return ''
    part = url.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]
    return part.lstrip('@').lower()


def save(report: dict) -> None:
    Path('publisher/connectivity-report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )


def main() -> int:
    cfg_path = Path(os.getenv('CLIENT_CONFIG', 'publisher/clients/f1-immobiliare.json'))
    if not cfg_path.exists():
        print(f'CONFIG_NOT_FOUND {cfg_path}')
        return 2

    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    expected = cfg.get('profile_urls', {})
    api_key = os.getenv('POSTIZ_API_KEY', '').strip()
    api_url = os.getenv('POSTIZ_API_URL', 'https://api.postiz.com/public/v1').rstrip('/')
    report = {
        'client': cfg.get('name'),
        'api_url': api_url,
        'expected': expected,
        'matches': {},
        'integrations': [],
    }

    if not api_key:
        report['error'] = 'POSTIZ_API_KEY missing'
        save(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3

    req = Request(api_url + '/integrations', headers={'Authorization': api_key, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        save(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 4

    if not isinstance(data, list):
        data = []

    report['integrations'] = [
        {k: item.get(k) for k in ('id', 'name', 'identifier', 'profile', 'disabled')}
        for item in data if isinstance(item, dict)
    ]

    connected_count = 0
    for platform, url in expected.items():
        wanted = handle_from_url(url)
        identifiers = {platform}
        if platform == 'instagram':
            identifiers.add('instagram-standalone')

        matches = []
        for item in data:
            if not isinstance(item, dict):
                continue
            identifier = str(item.get('identifier') or '').lower()
            profile = str(item.get('profile') or '').lstrip('@').lower()
            name = str(item.get('name') or '').lower().replace(' ', '')
            if identifier in identifiers and (
                not wanted or wanted == profile or wanted == name or wanted in profile or wanted in name
            ):
                matches.append({k: item.get(k) for k in ('id', 'name', 'identifier', 'profile', 'disabled')})

        report['matches'][platform] = {
            'expected_url': url,
            'expected_handle': wanted,
            'connected': bool(matches),
            'candidates': matches,
        }
        connected_count += int(bool(matches))

    report['connected_count'] = connected_count
    report['expected_count'] = len(expected)
    save(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
