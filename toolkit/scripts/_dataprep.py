"""Shared helpers for the Dataprep discovery scripts.

Centralizes the API behaviors proven in production (see
.gemini/skills/dataprep-migration/references/dataprep-api.md):
  - READ-ONLY: only GET. Never call any create/edit/delete/run endpoint.
  - Pagination limit=250 + flowsFilter/plansFilter=all (the 25-item silent-truncation trap).
  - Auth: `Authorization: Bearer <token>` from .env (never printed/committed).
  - Windows MAX_PATH-safe folder-name sanitization.
  - Lock-safe file writes (OneDrive WinError 32).

Stdlib only (urllib) so the sweep runs with no extra installs. .env is read locally.
NOTE: reconstructed from documented findings — smoke-test against your API version, as JSON
shapes (data wrappers, embedded fields) can vary by release.
"""
import os, re, json, pathlib, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env(path=ROOT / ".env"):
    """Minimal .env loader (no external dependency)."""
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DATAPREP_API_BASE_URL", "DATAPREP_API_TOKEN", "GCP_PROJECT"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


ENV = load_env()
BASE = ENV.get("DATAPREP_API_BASE_URL", "https://api.clouddataprep.com").rstrip("/")
TOKEN = ENV.get("DATAPREP_API_TOKEN", "")


def _get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def api_get(path, params=None):
    """GET <BASE>/<path>?<params>. READ-ONLY by contract — never pass a write endpoint."""
    url = f"{BASE}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return json.loads(_get(url).decode("utf-8"))


def api_list(path, extra=None, page_size=250):
    """Paginate a v4 list endpoint. Always limit=250 (avoids the 25-item silent cap);
    pass ownership filters (e.g. flowsFilter=all) so team/ex-employee resources are included."""
    out, offset = [], 0
    while True:
        params = {"limit": page_size, "offset": offset}
        params.update(extra or {})
        data = api_get(path, params)
        items = data.get("data", data) if isinstance(data, dict) else data
        items = items or []
        out.extend(items)
        if len(items) < page_size:
            return out
        offset += page_size


def download_bytes(path):
    """GET a binary resource (e.g. a flow package ZIP)."""
    return _get(f"{BASE}/{path.lstrip('/')}")


_SAN = re.compile(r"[^a-zA-Z0-9_.\-]")
def sanitize_name(name, maxlen=60):
    """Windows MAX_PATH-safe folder name: <=60 chars, [a-zA-Z0-9_.-], collapse repeats,
    no flow-ID suffixes. Keeps directory trees shallow so extraction doesn't silently fail."""
    s = _SAN.sub("_", str(name))
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:maxlen].strip("_") or "unnamed"


def safe_write_bytes(path, data):
    """Write bytes; on a OneDrive/Excel lock (PermissionError / WinError 32) write a fallback name."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(data)
        return path
    except PermissionError:
        alt = path.with_name(path.stem + "_fallback" + path.suffix)
        alt.write_bytes(data)
        print(f"  [locked] wrote fallback: {alt}")
        return alt


def safe_write_text(path, text):
    return safe_write_bytes(path, text.encode("utf-8"))
