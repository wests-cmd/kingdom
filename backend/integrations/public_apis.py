"""Untrusted discovery metadata, separate from a small reviewed execution allowlist."""
import hashlib
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import time
from urllib.parse import urlsplit

from backend.integrations.provider import ProviderRegistry
from backend.storage.integration_repository import IntegrationRepository

CATALOG_URL = "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
REVIEWED = {
    "openfoodfacts": {"url": "https://world.openfoodfacts.org/api/v2/product/3017620422003.json?fields=code,product_name",
                      "keys": {"code": str, "status": int, "product": dict}, "capabilities": ["product_research"],
                      "documentation": "https://openfoodfacts.github.io/openfoodfacts-server/api/ref-cheatsheet/"},
    "open-meteo": {"url": "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m",
                   "keys": {"latitude": (int, float), "longitude": (int, float), "current": dict},
                   "capabilities": ["weather_metadata"], "documentation": "https://open-meteo.com/en/docs"},
}
registry = ProviderRegistry(IntegrationRepository())


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = {record[4][0] for record in socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast for address in addresses):
            raise ValueError("Non-public provider DNS address rejected")
        # Resolve once; connect to that exact validated address with hostname certificate verification.
        sock = socket.create_connection((sorted(addresses)[0], self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def safe_get(url, max_bytes=131072, timeout=10):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment or parts.port not in (None, 443):
        raise ValueError("Only public HTTPS on port 443 is supported")
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("IP literal endpoints are not supported")
    connection = PinnedHTTPSConnection(parts.hostname, timeout=timeout, context=ssl.create_default_context())
    try:
        connection.request("GET", parts.path + ("?" + parts.query if parts.query else ""), headers={"Accept": "application/json", "User-Agent": "Kingdom-readonly-probe/1"})
        response = connection.getresponse()
        if response.status != 200:  # Includes redirects: never follow them.
            raise ValueError("Provider returned an unsuccessful HTTP status")
        content_type = response.getheader("Content-Type", "").split(";")[0].strip().lower()
        length = response.getheader("Content-Length")
        if length and int(length) > max_bytes:
            raise ValueError("Provider response exceeds size limit")
        deadline, body = time.monotonic() + timeout, bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Provider response deadline exceeded")
            if connection.sock:
                connection.sock.settimeout(remaining)
            chunk = response.read1(min(8192, max_bytes + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ValueError("Provider response exceeds size limit")
        return bytes(body), content_type
    finally:
        connection.close()


def parse_catalog(markdown):
    if len(markdown.encode()) > 1500000:
        raise ValueError("Catalog exceeds size limit")
    category, active, result = "", False, {}
    for line in markdown.splitlines():
        if line.startswith("### "):
            category, active = line[4:].strip(), False
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells == ["API", "Description", "Auth", "HTTPS", "CORS"]:
            active = True
            continue
        if not active or len(cells) != 5:
            continue
        match = re.fullmatch(r"\[([^\]]{1,100})\]\((https://[^\s)]+)\)", cells[0])
        if not match or cells[3] not in ("Yes", "No"):
            continue
        name, docs = match.groups()
        parts = urlsplit(docs)
        if not parts.hostname or parts.username or parts.password:
            continue
        identifier = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50]
        identifier += "-" + hashlib.sha256(docs.encode()).hexdigest()[:8]
        # Catalog claims never activate tools, grant capabilities, or verify health.
        result[identifier] = {"provider_id": identifier, "name": name, "category": category[:100],
                              "documentation": docs, "authentication": "none" if not cells[2] else "required",
                              "https_claimed": cells[3] == "Yes", "cors_claim": cells[4][:30],
                              "source": "public-apis/public-apis", "state": "discovered", "executable": False}
    return list(result.values())


def refresh_catalog():
    body, _ = safe_get(CATALOG_URL, max_bytes=1500000)
    entries = parse_catalog(body.decode("utf-8"))
    if not entries:
        raise ValueError("No recognized catalog table; existing catalog preserved")
    for entry in entries:
        registry.save_catalog_entry(entry)
    return {"count": len(entries), "sha256": hashlib.sha256(body).hexdigest(), "source": CATALOG_URL}


def validate_provider_response(provider_id, body, content_type):
    spec = REVIEWED.get(provider_id)
    if not spec or content_type != "application/json":
        raise ValueError("Unreviewed provider or unexpected content type")
    def invalid_number(_):
        raise ValueError("Non-finite provider JSON number")
    value = json.loads(body, parse_constant=invalid_number)
    if not isinstance(value, dict) or any(not isinstance(value.get(key), kind) or isinstance(value.get(key), bool) for key, kind in spec["keys"].items()):
        raise ValueError("Provider response does not match reviewed metadata schema")
    if provider_id == "openfoodfacts" and (value["status"] != 1 or value["code"] != "3017620422003" or not isinstance(value["product"].get("product_name"), str) or not value["product"]["product_name"].strip() or len(value["product"]["product_name"]) > 500):
        raise ValueError("Reviewed product metadata is missing")
    if provider_id == "open-meteo":
        temperature = value["current"].get("temperature_2m")
        if type(temperature) not in (int, float) or not math.isfinite(temperature) or not -90 <= value["latitude"] <= 90 or not -180 <= value["longitude"] <= 180 or not isinstance(value["current"].get("time"), str):
            raise ValueError("Reviewed weather metadata is missing")
    return {"provider_id": provider_id, "capabilities": spec["capabilities"],
            "response_sha256": hashlib.sha256(body).hexdigest(), "status": "verified", "read_only": True}


def probe_provider(provider_id, timeout=10):
    if provider_id not in REVIEWED:
        raise ValueError("Provider has no reviewed read-only test")
    if type(timeout) is not int or not 1 <= timeout <= 15:
        raise ValueError("Provider timeout must be between 1 and 15 seconds")
    settings = registry.repository.get("provider_settings", provider_id)
    if not settings or not settings.get("enabled"):
        raise PermissionError("Provider must be explicitly enabled by the owner")
    started = time.monotonic()
    body, content_type = safe_get(REVIEWED[provider_id]["url"], timeout=timeout)
    summary = validate_provider_response(provider_id, body, content_type)
    return {"summary": summary, "body": body.decode("utf-8"), "content_type": content_type,
            "latency_ms": round((time.monotonic() - started) * 1000), "dns_public": True, "tls_verified": True,
            "http_status": 200}
