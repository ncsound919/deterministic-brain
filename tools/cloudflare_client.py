"""Cloudflare client — Pages deployment, Workers, DNS.

Action-out: deploys built artifacts to Cloudflare after scaffold pipeline completes.
Requires CF_API_TOKEN + CF_ACCOUNT_ID env vars.

Token savings: ~350 tokens per deploy call vs LLM-generated curl.
"""

from __future__ import annotations
import os
from typing import Dict, List

from tools.api_client import AuthenticatedClient
from tools.vault_aware_api import get_key

CF_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareClient:
    def __init__(self, token: str = "", account_id: str = ""):
        self.token = get_key(
            vault_category="cloudflare", vault_key="api_token",
            env_var="CF_API_TOKEN", explicit=token,
        )
        self.account_id = get_key(
            vault_category="cloudflare", vault_key="account_id",
            env_var="CF_ACCOUNT_ID", explicit=account_id,
        )
        self.client = AuthenticatedClient(
            base_url=CF_BASE,
            api_key=self.token,
            auth_header="Authorization",
            auth_prefix="Bearer ",
        )

    def list_pages_projects(self) -> Dict:
        return self.client.get(f"/accounts/{self.account_id}/pages/projects")

    def deploy_pages(self, project: str, branch: str = "main") -> Dict:
        return self.client.post(
            f"/accounts/{self.account_id}/pages/projects/{project}/deployments",
            data={"branch": branch},
        )

    def list_workers(self) -> Dict:
        return self.client.get(f"/accounts/{self.account_id}/workers/services")

    def update_dns(self, zone_id: str, name: str, content: str,
                   record_type: str = "CNAME", proxied: bool = True) -> Dict:
        return self.client.post(
            f"/zones/{zone_id}/dns_records",
            data={
                "type": record_type, "name": name,
                "content": content, "proxied": proxied, "ttl": 1,
            },
        )

    def list_zones(self) -> Dict:
        return self.client.get("/zones")

    def purge_cache(self, zone_id: str) -> Dict:
        return self.client.post(
            f"/zones/{zone_id}/purge_cache",
            data={"purge_everything": True},
        )
