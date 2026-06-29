"""Add correlation-key field indexes to the SLS logstore (run_id / thread_id /
user_id / trace_id).

Motivation: without field indexes the patrol tools can only full-text query
``"RUN_ID"``; they cannot do ``run_id: "..."`` exact match or cross-stream join.
This adds them, mirroring an existing key's token config.

Safety:
  - **Default dry-run (read-only)**: prints which keys would be added; ``--apply``
    actually calls update_index.
  - Idempotent: existing keys are untouched, only missing ones are added; full-text
    index and other keys are preserved.
  - Never prints AK/SK. Uses the backend settings credentials.

Two field gotchas:
  - History is not retroactive: indexes take effect from their activation time; logs
    written earlier still fall back to full-text.
  - Propagation delay: a read-back is immediate, but the query engine takes ~1 min;
    field queries may briefly raise ``ParameterInvalid`` — a delay, not misconfig.

Usage:
    cd backend && .venv/bin/python scripts/sls_add_field_index.py            # dry-run
    cd backend && .venv/bin/python scripts/sls_add_field_index.py --apply    # write
"""

from __future__ import annotations

import argparse
import sys

from app.core.settings import get_settings

TARGET_KEYS = ["run_id", "thread_id", "user_id", "trace_id"]
# Tokens deliberately exclude '-' and '_' so a full nanoid/uuid stays exact-queryable.
_DEFAULT_TOKENS = [
    ",", " ", "'", '"', ";", "\\", "$", "#", "!", "=", "(", ")", "[", "]",
    "{", "}", "?", "@", "&", "<", ">", "/", ":", "\n", "\t", "\r",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Add SLS correlation-key field indexes (default dry-run)")
    ap.add_argument("--apply", action="store_true", help="actually write (else read-only dry-run)")
    args = ap.parse_args()

    s = get_settings()
    if not (s.sls_enabled and s.sls_endpoint and s.sls_access_key_id and s.sls_project):
        raise SystemExit("SLS not configured (set sls_enabled + endpoint/keys/project). See settings.")
    from aliyun.log import IndexKeyConfig, LogClient

    client = LogClient(s.sls_endpoint, s.sls_access_key_id, s.sls_access_key_secret)
    print(f"project/logstore = {s.sls_project}/{s.sls_logstore}")

    idx = client.get_index_config(s.sls_project, s.sls_logstore).get_index_config()
    data = idx.to_json()
    keys = data.get("keys") or {}
    print(f"full_text_index  = {bool(data.get('line'))}")
    print(f"existing_keys    = {len(keys)}")

    # Mirror an existing key's token config when present; else the default table.
    mirror = next((keys[k] for k in TARGET_KEYS if k in keys), {})
    token_list = mirror.get("token") or _DEFAULT_TOKENS
    case_sensitive = bool(mirror.get("caseSensitive", False))
    doc_value = bool(mirror.get("doc_value", True))

    missing = [k for k in TARGET_KEYS if k not in keys]
    present = [k for k in TARGET_KEYS if k in keys]
    if present:
        print(f"already_indexed  = {present}")
    if not missing:
        print("✓ all target keys already have field indexes, nothing to change.")
        return 0
    print(f"will_add         = {missing}  (type=text, doc_value={doc_value})")

    if not args.apply:
        print("\n[DRY-RUN] not written. Add --apply once confirmed.")
        return 0

    for k in missing:
        idx.key_config_list[k] = IndexKeyConfig(
            token_list=list(token_list),
            case_sensitive=case_sensitive,
            index_type="text",
            doc_value=doc_value,
        )
    client.update_index(s.sls_project, s.sls_logstore, idx)
    print("update_index submitted, reading back…")

    after = client.get_index_config(s.sls_project, s.sls_logstore).get_index_config().to_json()
    after_keys = after.get("keys") or {}
    ok = [k for k in TARGET_KEYS if k in after_keys]
    print(f"after_indexed    = {ok}")
    if all(k in after_keys for k in TARGET_KEYS):
        print("✓ all target keys indexed (new logs are run_id: \"...\" queryable; history per index activation time).")
        return 0
    print("✗ still missing:", [k for k in TARGET_KEYS if k not in after_keys])
    return 1


if __name__ == "__main__":
    sys.exit(main())
