"""env_monitor.py

Lightweight environment/service health checks for external dependencies.

Provides conservative, import-safe probes for Qdrant, Neo4j, and generic
HTTP endpoints. Use for startup checks or periodic monitoring.
"""
from __future__ import annotations
import socket
from typing import Dict, Optional


class EnvMonitor:
    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def _tcp_connect(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=self.timeout):
                return True
        except Exception:
            return False

    def check_qdrant(self, host: str = "localhost", port: int = 6333) -> Dict[str, object]:
        """Check Qdrant service by TCP connect or qdrant-client ping if available."""
        try:
            from qdrant_client import QdrantClient  # type: ignore
            c = QdrantClient(host=host, port=port, timeout=self.timeout)
            # minimal call; may raise if unreachable
            c.get_collections()
            return {"ok": True, "method": "qdrant_client"}
        except Exception:
            # fallback to TCP socket
            ok = self._tcp_connect(host, port)
            return {"ok": ok, "method": "tcp_fallback", "host": host, "port": port}

    def check_neo4j(self, uri: str = "bolt://localhost:7687") -> Dict[str, object]:
        """Check Neo4j by attempting to create a driver or TCP connect to the host:port."""
        try:
            from neo4j import GraphDatabase  # type: ignore
            # parse host:port
            if uri.startswith("bolt://"):
                hostport = uri[len("bolt://") :]
            else:
                hostport = uri
            host, port = hostport.split(":")[:2]
            # Try a TCP connect first
            ok = self._tcp_connect(host, int(port))
            return {"ok": ok, "method": "tcp", "uri": uri}
        except Exception:
            return {"ok": False, "method": "none", "uri": uri}

    def check_http(self, url: str) -> Dict[str, object]:
        try:
            import requests  # type: ignore
            r = requests.get(url, timeout=self.timeout)
            return {"ok": r.status_code == 200, "status_code": r.status_code}
        except Exception:
            # fallback: resolve host
            try:
                from urllib.parse import urlparse
                p = urlparse(url)
                host = p.hostname or ""
                port = p.port or (443 if p.scheme == "https" else 80)
                ok = self._tcp_connect(host, port)
                return {"ok": ok, "method": "tcp_fallback", "host": host, "port": port}
            except Exception:
                return {"ok": False}

    def check_all(self, config: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, object]]:
        """Run configured checks. Example config keys: qdrant, neo4j, ui.
        config = {"qdrant": "host:port", "neo4j": "bolt://host:port", "ui": "http://localhost:3000"}
        """
        config = config or {}
        out: Dict[str, Dict[str, object]] = {}
        if "qdrant" in config:
            hostport = config["qdrant"].split(":")
            host = hostport[0]
            port = int(hostport[1]) if len(hostport) > 1 else 6333
            out["qdrant"] = self.check_qdrant(host, port)
        if "neo4j" in config:
            out["neo4j"] = self.check_neo4j(config["neo4j"])
        if "ui" in config:
            out["ui"] = self.check_http(config["ui"])
        return out


__all__ = ["EnvMonitor"]
