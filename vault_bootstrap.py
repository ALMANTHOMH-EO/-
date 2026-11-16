"""Production entry point: verify EO INTEGRITY SEAL, decrypt to tmpfs, run API."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from eo_vault_runtime import VaultError, decrypt_to_directory


def main() -> int:
    root = Path(__file__).resolve().parent
    vault_dir = Path(os.getenv("EO_VAULT_DIR", str(root / "vault"))).resolve()
    runtime_dir = Path(os.getenv("EO_VAULT_RUNTIME_DIR", "/run/eo-runtime")).resolve()
    master = os.getenv("EO_MASTER_KEY", "")
    if not master:
        print("EO VAULT: EO_MASTER_KEY is required; refusing plaintext fallback.", file=sys.stderr)
        return 78
    try:
        if runtime_dir.exists() and any(runtime_dir.iterdir()):
            print("EO VAULT: runtime directory is not empty; refusing overwrite.", file=sys.stderr)
            return 78
        runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        decrypt_to_directory(vault_dir, master, runtime_dir)
    except (VaultError, OSError) as exc:
        print(f"EO VAULT startup blocked: {exc}", file=sys.stderr)
        return 78
    os.chdir(runtime_dir)
    os.environ["PYTHONPATH"] = str(runtime_dir) + os.pathsep + os.getenv("PYTHONPATH", "")
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "8000"), "--proxy-headers", "--forwarded-allow-ips=127.0.0.1,172.16.0.0/12"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
