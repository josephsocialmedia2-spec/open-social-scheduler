#!/usr/bin/env python3
"""Provision the Open Social Scheduler / Postiz host on Hetzner Cloud.

Idempotent by server name. Optionally syncs the public A record in Cloudflare.
Secrets are read only from environment variables and are never written to the repo.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path

import requests
from hcloud import Client
from hcloud.images import Image
from hcloud.locations import Location
from hcloud.server_types import ServerType
from hcloud.ssh_keys import SSHKey

TOKEN = os.getenv("HCLOUD_TOKEN", "").strip()
SERVER_NAME = os.getenv("POSTIZ_SERVER_NAME", "open-social-postiz").strip()
SERVER_TYPE = os.getenv("POSTIZ_SERVER_TYPE", "cx33").strip()
IMAGE = os.getenv("POSTIZ_SERVER_IMAGE", "ubuntu-24.04").strip()
LOCATION = os.getenv("POSTIZ_SERVER_LOCATION", "nbg1").strip()
DOMAIN = os.getenv("POSTIZ_DOMAIN", "social.realmediapro.it").strip()
SSH_PUBLIC_KEY = os.getenv("POSTIZ_SSH_PUBLIC_KEY", "").strip()
REPO = os.getenv(
    "OPEN_SOCIAL_REPO",
    "https://github.com/josephsocialmedia2-spec/open-social-scheduler.git",
).strip()

CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CF_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "").strip()


def cloud_init() -> str:
    return textwrap.dedent(
        f"""\
        #cloud-config
        package_update: true
        packages:
          - git
          - curl
          - ca-certificates
          - ufw
        write_files:
          - path: /usr/local/sbin/open-social-update
            owner: root:root
            permissions: '0755'
            content: |
              #!/usr/bin/env bash
              set -euo pipefail
              cd /opt/open-social-scheduler
              git fetch origin main
              git reset --hard origin/main
              bash postiz-stack/bootstrap_postiz.sh
              bash postiz-stack/start_postiz.sh
          - path: /etc/systemd/system/open-social-update.service
            owner: root:root
            permissions: '0644'
            content: |
              [Unit]
              Description=Update Open Social Scheduler and Postiz
              After=docker.service network-online.target
              Wants=network-online.target

              [Service]
              Type=oneshot
              ExecStart=/usr/local/sbin/open-social-update
          - path: /etc/systemd/system/open-social-update.timer
            owner: root:root
            permissions: '0644'
            content: |
              [Unit]
              Description=Daily Open Social Scheduler update

              [Timer]
              OnCalendar=*-*-* 04:30:00 Europe/Rome
              Persistent=true
              RandomizedDelaySec=300

              [Install]
              WantedBy=timers.target
        runcmd:
          - [ bash, -lc, "ufw default deny incoming && ufw default allow outgoing && ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable" ]
          - [ bash, -lc, "rm -rf /opt/open-social-scheduler && git clone {REPO} /opt/open-social-scheduler" ]
          - [ bash, -lc, "cd /opt/open-social-scheduler && POSTIZ_DOMAIN={DOMAIN} bash postiz-stack/install_production_ubuntu.sh > /var/log/open-social-install.log 2>&1" ]
          - [ bash, -lc, "systemctl daemon-reload && systemctl enable --now open-social-update.timer" ]
        final_message: "Open Social Scheduler bootstrap complete"
        """
    )


def sync_cloudflare(ipv4: str) -> None:
    if not CF_TOKEN or not CF_ZONE_ID:
        print("Cloudflare DNS credentials not configured; DNS sync skipped.")
        return

    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json",
    }
    base = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    response = requests.get(
        base,
        headers=headers,
        params={"type": "A", "name": DOMAIN},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"Cloudflare DNS lookup failed: {payload}")

    body = {
        "type": "A",
        "name": DOMAIN,
        "content": ipv4,
        "ttl": 1,
        "proxied": False,
        "comment": "Open Social Scheduler / Postiz origin",
    }
    matches = payload.get("result") or []
    if matches:
        record_id = matches[0]["id"]
        result = requests.patch(
            f"{base}/{record_id}", headers=headers, json=body, timeout=30
        )
    else:
        result = requests.post(base, headers=headers, json=body, timeout=30)
    result.raise_for_status()
    data = result.json()
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare DNS write failed: {data}")
    print(f"Cloudflare A record ready: {DOMAIN} -> {ipv4}")


def main() -> int:
    if not TOKEN:
        print("HCLOUD_TOKEN is required.", file=sys.stderr)
        return 2

    client = Client(
        token=TOKEN,
        application_name="open-social-scheduler",
        application_version="1.0",
    )

    server = client.servers.get_by_name(SERVER_NAME)
    if server is None:
        ssh_keys = None
        if SSH_PUBLIC_KEY:
            key_name = f"{SERVER_NAME}-deploy"
            bound_key = client.ssh_keys.get_by_name(key_name)
            if bound_key is None:
                bound_key = client.ssh_keys.create(
                    name=key_name, public_key=SSH_PUBLIC_KEY
                )
            ssh_keys = [SSHKey(id=bound_key.id)]

        print(
            f"Creating {SERVER_NAME}: {SERVER_TYPE}, {IMAGE}, location {LOCATION}"
        )
        response = client.servers.create(
            name=SERVER_NAME,
            server_type=ServerType(name=SERVER_TYPE),
            image=Image(name=IMAGE),
            location=Location(name=LOCATION),
            ssh_keys=ssh_keys,
            user_data=cloud_init(),
            labels={
                "service": "open-social-scheduler",
                "role": "postiz",
                "managed-by": "github-actions",
            },
            start_after_create=True,
        )
        server = response.server
        if response.root_password:
            print(
                "Server created without an injected SSH key. Hetzner generated a root password; "
                "retrieve/manage it securely in your Hetzner account. It is intentionally not printed here."
            )
    else:
        print(f"Server {SERVER_NAME} already exists; reusing it.")

    server = client.servers.get_by_id(server.id)
    ipv4 = server.public_net.ipv4.ip if server and server.public_net.ipv4 else ""
    if not ipv4:
        raise RuntimeError("Server has no public IPv4 address")

    sync_cloudflare(ipv4)

    output = {
        "server_id": server.id,
        "server_name": server.name,
        "server_type": server.server_type.name if server.server_type else SERVER_TYPE,
        "location": server.location.name if server.location else LOCATION,
        "ipv4": ipv4,
        "domain": DOMAIN,
        "postiz_url": f"https://{DOMAIN}",
    }
    Path("/tmp/postiz-provision.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
