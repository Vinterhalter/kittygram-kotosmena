"""Run a complete scenario over real HTTP. No persistent credentials in evidence."""

import json, re, sys, time, secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError

root = Path(__file__).resolve().parents[1]
base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("http-demo.json")
now = datetime.now(timezone.utc)
suffix = str(time.time_ns())
values = {
    "owner_username": "owner_" + suffix,
    "sitter_username": "sitter_" + suffix,
    "password": secrets.token_urlsafe(24),
    "starts_at": (now - timedelta(hours=1)).isoformat(),
    "due_at": (now + timedelta(hours=1)).isoformat(),
    "ends_at": (now + timedelta(days=1)).isoformat(),
    "extended_at": (now + timedelta(days=2)).isoformat(),
}


def subst(value):
    if isinstance(value, str):
        return re.sub(r"\{\{(\w+)\}\}", lambda m: str(values[m[1]]), value)
    if isinstance(value, dict):
        return {k: subst(v) for k, v in value.items()}
    return value


results = []
for step in json.loads((root / "docs/demo_steps.json").read_text()):
    payload = subst(step["data"])
    path = subst(step["path"])
    headers = {}
    if step["role"]:
        headers["Authorization"] = "Token " + values[step["role"] + "_token"]
    body = None
    if payload:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    req = Request(
        base + quote(path, safe="/:?=&%"),
        data=body,
        headers=headers,
        method=step["method"],
    )
    try:
        response = urlopen(req)
    except HTTPError as e:
        response = e
    raw = response.read().decode()
    status = response.code
    try:
        data = json.loads(raw)
    except ValueError:
        data = {
            "content_type": response.headers.get("Content-Type"),
            "bytes": len(raw.encode()),
        }
    if step["save"]:
        values[step["save"][0]] = data[step["save"][1]]
    if isinstance(data, dict) and "auth_token" in data:
        data["auth_token"] = "[REDACTED]"
    public_payload = payload.copy() if isinstance(payload, dict) else payload
    if isinstance(public_payload, dict) and "password" in public_payload:
        public_payload["password"] = "[REDACTED]"
    results.append(
        {
            "name": step["name"],
            "method": step["method"],
            "path": path,
            "role": step["role"],
            "request": public_payload,
            "expected": step["code"],
            "status": status,
            "passed": status == step["code"],
            "response": data,
        }
    )
    print(f"{status} {step['method']:5} {path} — {step['name']}")
    if status != step["code"]:
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit("Unexpected response: " + raw[:500])
out.write_text(
    json.dumps(
        {"created_at": now.isoformat(), "base_url": base, "checks": results},
        ensure_ascii=False,
        indent=2,
    )
)
print(f"PASS {len(results)}/{len(results)}")
