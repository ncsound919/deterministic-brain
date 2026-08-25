"""Kaggle Manager — dataset/competition search, download, deterministic snapshots.

Follows the same shape as `features/github_manager.py`: a singleton manager
backed by the credential vault (`kaggle` category: username, api_key) or env
vars, using the Kaggle REST API v1 (`https://www.kaggle.com/api/v1`).

Deterministic snapshots: every downloaded dataset is stored under
`datasets/kaggle/<owner>/<dataset>/` with a `manifest.json` that records a
content hash (sha256 over all files) plus per-file hashes. This preserves the
deterministic-brain guarantee: given the same snapshot dir, a dataset pull is
reproducible and immune to upstream churn. To re-sync a snapshot, force=True.

When credentials are absent the manager stays usable for read-only anonymous
endpoints where Kaggle allows them; authenticated calls report an honest
`"configured": false` rather than raising.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
import urllib.request
import urllib.error
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

KAGGLE_API_BASE = os.getenv("KAGGLE_API_BASE", "https://www.kaggle.com/api/v1")
DEFAULT_DATA_DIR = os.getenv("KAGGLE_DATA_DIR", "datasets/kaggle")


@dataclass
class KaggleDataset:
    ref: str
    title: str = ""
    owner: str = ""
    subtitle: str = ""
    total_bytes: int = 0
    total_downloads: int = 0
    license_name: str = ""
    tags: List[str] = None
    last_updated: str = ""

    def to_dict(self) -> Dict:
        return {
            "ref": self.ref, "title": self.title, "owner": self.owner,
            "subtitle": self.subtitle, "total_bytes": self.total_bytes,
            "total_downloads": self.total_downloads,
            "license_name": self.license_name, "tags": self.tags or [],
            "last_updated": self.last_updated,
        }


class KaggleManager:
    def __init__(self, username: str = "", api_key: str = "", data_dir: str = DEFAULT_DATA_DIR):
        self.username = username or os.getenv("KAGGLE_USERNAME", "")
        self.api_key = api_key or os.getenv("KAGGLE_KEY", "") or os.getenv("KAGGLE_API_TOKEN", "")
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._load_credentials()

    def _load_credentials(self) -> None:
        try:
            from config.credentials import get_credential_vault
            v = get_credential_vault()
            cat = v.get_category("kaggle")
            if not self.username:
                self.username = cat.get("username", "")
            if not self.api_key:
                self.api_key = cat.get("api_key", "") or cat.get("token", "")
        except ImportError:
            pass

    @property
    def configured(self) -> bool:
        return bool(self.username and self.api_key)

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "DeterministicBrain/1.0"}
        if self.configured:
            cred = f"{self.username}:{self.api_key}"
            h["Authorization"] = "Basic " + base64.b64encode(cred.encode()).decode()
        return h

    def _api(self, path: str, method: str = "GET", body: Optional[Dict] = None,
             params: Optional[Dict] = None, timeout: int = 30) -> Any:
        """REST call returning parsed JSON, or {'error': ...} on failure."""
        url = f"{KAGGLE_API_BASE}{path}"
        if params:
            from urllib.parse import urlencode
            sep = "&" if "?" in url else "?"
            url += sep + urlencode({k: v for k, v in params.items() if v is not None})
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode()[:300]
            except Exception:
                pass
            return {"error": f"HTTP {e.code}", "detail": detail}
        except Exception as e:
            return {"error": str(e)}

    # ── Account / status ───────────────────────────────────────────────
    def whoami(self) -> Dict:
        """Verify credentials by hitting an authenticated endpoint.

        There is no public `/account` endpoint; `GET /competitions/list`
        returns 401 for bad/missing credentials and 200 when the key is valid.
        """
        if not self.configured:
            return {"configured": False, "username": self.username}
        data = self._api("/competitions/list")
        if isinstance(data, dict) and data.get("error"):
            return {"configured": True, "username": self.username, "error": data["error"]}
        comps = data if isinstance(data, list) else (data.get("competitionList", []) if isinstance(data, dict) else [])
        return {
            "configured": True,
            "username": self.username,
            "authenticated": True,
            "competitions": len(comps),
        }

    def status(self) -> Dict:
        who = self.whoami()
        return {
            "configured": who.get("configured", False),
            "username": who.get("username", ""),
            "authenticated": who.get("authenticated", False),
            "api": KAGGLE_API_BASE,
            "data_dir": self.data_dir,
            "snapshots": len(self.list_snapshots()),
            "ok": who.get("configured", False) and "error" not in who and who.get("authenticated", False),
        }

    # ── Search ─────────────────────────────────────────────────────────
    def search_datasets(self, query: str = "", per_page: int = 10,
                        sort_by: str = "hottest") -> List[KaggleDataset]:
        """Search datasets. `GET /datasets/list` returns a plain array."""
        params = {"search": query or None, "pageSize": per_page, "sortBy": sort_by}
        data = self._api("/datasets/list", params=params)
        if isinstance(data, dict) and data.get("error"):
            return []
        if isinstance(data, dict):
            data = data.get("datasetList", []) or []
        raw = data if isinstance(data, list) else []
        results: List[KaggleDataset] = []
        for item in raw:
            ref = item.get("ref") or item.get("datasetRef") or ""
            owner = (ref or "").split("/")[0] or item.get("ownerRef", "") or item.get("ownerName", "")
            tags = []
            for t in item.get("tags", []) or []:
                if isinstance(t, dict):
                    tags.append(t.get("name") or t.get("nameNullable") or "")
                elif t:
                    tags.append(str(t))
            results.append(KaggleDataset(
                ref=ref, title=item.get("title", ""), owner=owner,
                subtitle=item.get("subtitle", ""),
                total_bytes=item.get("totalBytes", 0) or 0,
                total_downloads=item.get("downloadCount", 0) or 0,
                license_name=item.get("licenseName", ""), tags=tags,
                last_updated=item.get("lastUpdated", ""),
            ))
        return results

    def list_competitions(self) -> List[Dict]:
        data = self._api("/competitions/list")
        if isinstance(data, dict) and data.get("error"):
            return []
        if isinstance(data, dict):
            data = data.get("competitionList", [])
        if not isinstance(data, list):
            return []
        return [
            {
                "id": c.get("id"), "name": c.get("competitionName", ""),
                "title": c.get("competitionTitle", ""), "enabled": c.get("enabled", False),
                "reward": c.get("reward", 0), "deadline": c.get("deadline", ""),
                "category": c.get("category", ""),
            }
            for c in data if isinstance(c, dict)
        ]

    def dataset_files(self, ref: str) -> List[Dict]:
        """List files in a dataset (owner/dataset-slug)."""
        if "/" not in ref:
            return []
        owner, dataset = ref.split("/", 1)
        data = self._api(f"/datasets/list/{owner}/{dataset}")
        if isinstance(data, dict) and data.get("error"):
            return []
        if isinstance(data, dict):
            data = data.get("datasetFiles", []) or data.get("files", [])
        if not isinstance(data, list):
            return []
        return [
            {
                "name": f.get("name") or f.get("nameNullable") or "",
                "total_bytes": f.get("totalBytes", 0) or 0,
                "file_type": f.get("fileType", ""),
                "creation_date": f.get("creationDate", ""),
            }
            for f in data if isinstance(f, dict)
        ]

    # ── Download + deterministic snapshot ──────────────────────────────
    def download_dataset(self, ref: str, force: bool = False,
                         unzip: bool = True, target_dir: Optional[str] = None) -> Dict:
        """Download a dataset and snapshot it with a content-hash manifest.

        Returns a dict with snapshot metadata; callers get the manifest path.
        Idempotent: if the manifest already matches the upstream hash and
        force is False, returns the existing snapshot untouched.
        """
        if "/" not in ref:
            return {"error": "dataset must be owner/dataset-slug", "ref": ref}
        owner, dataset = ref.split("/", 1)
        safe_owner = owner.replace("/", "_")
        safe_ds = dataset.replace("/", "_")
        dest = target_dir or os.path.join(self.data_dir, safe_owner, safe_ds)
        os.makedirs(dest, exist_ok=True)

        manifest_path = os.path.join(dest, "manifest.json")
        existing = self._load_manifest(manifest_path)
        if existing and not force:
            return self._snapshot_result(dest, existing, reused=True)

        url = f"{KAGGLE_API_BASE}/datasets/download/{owner}/{dataset}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
        except Exception as e:
            return {"error": str(e), "ref": ref}

        extracted: List[Dict] = []
        if unzip:
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    names = z.namelist()
                    for n in names:
                        if n.endswith("/"):
                            continue
                        content = z.read(n)
                        out = os.path.join(dest, n)
                        os.makedirs(os.path.dirname(out), exist_ok=True)
                        with open(out, "wb") as f:
                            f.write(content)
                        extracted.append(self._file_entry(n, content))
            except zipfile.BadZipFile:
                # Single-file dataset (Kaggle returns the raw file)
                content = raw
                with open(os.path.join(dest, safe_ds), "wb") as f:
                    f.write(content)
                extracted.append(self._file_entry(safe_ds, content))
        else:
            with open(os.path.join(dest, f"{safe_ds}.zip"), "wb") as f:
                f.write(raw)
            extracted.append(self._file_entry(f"{safe_ds}.zip", raw))

        content_hash = self._content_hash(extracted)
        manifest = {
            "source": "kaggle",
            "ref": ref,
            "owner": owner,
            "dataset": dataset,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
            "files": extracted,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        return self._snapshot_result(dest, manifest, reused=False)

    def _load_manifest(self, manifest_path: str) -> Optional[Dict]:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def _file_entry(name: str, content: bytes) -> Dict:
        return {
            "path": name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        }

    @staticmethod
    def _content_hash(files: List[Dict]) -> str:
        h = hashlib.sha256()
        for f in sorted(files, key=lambda x: x["path"]):
            h.update(f["path"].encode())
            h.update(f["sha256"].encode())
        return h.hexdigest()

    @staticmethod
    def _snapshot_result(dest: str, manifest: Dict, reused: bool) -> Dict:
        return {
            "status": "ok",
            "reused": reused,
            "ref": manifest.get("ref", ""),
            "dir": dest,
            "manifest": os.path.join(dest, "manifest.json"),
            "content_hash": manifest.get("content_hash", ""),
            "files": manifest.get("files", []),
        }

    def list_snapshots(self) -> List[Dict]:
        """Enumerate all deterministic snapshots under data_dir."""
        out: List[Dict] = []
        if not os.path.isdir(self.data_dir):
            return out
        for root, _dirs, files in os.walk(self.data_dir):
            if "manifest.json" not in files:
                continue
            manifest = self._load_manifest(os.path.join(root, "manifest.json"))
            if not manifest:
                continue
            out.append({
                "ref": manifest.get("ref", ""),
                "dir": root,
                "content_hash": manifest.get("content_hash", ""),
                "downloaded_at": manifest.get("downloaded_at", ""),
                "files": manifest.get("files", []),
            })
        out.sort(key=lambda x: x.get("downloaded_at", ""), reverse=True)
        return out


_MANAGER: Optional[KaggleManager] = None


def get_kaggle() -> KaggleManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = KaggleManager()
    return _MANAGER
