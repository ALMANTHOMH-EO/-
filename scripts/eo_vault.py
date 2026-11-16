#!/usr/bin/env python3
"""EO VAULT tools: generate keys, seal sources, verify, and decrypt as developer.

Never store .eo-vault-keys or the master/signing private keys in Git, CI artifacts,
container images, or the sealed release package.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from eo_vault_runtime import (  # noqa: E402
    AAD, CIPHER_ID, CIPHER_NAME, FORMAT_VERSION, MAGIC, SIGNATURE_NAME,
    HASH_NAME, VaultError, canonical_json, decrypt_to_directory,
    load_master_key, sha256, verify_bundle,
)

PAYLOAD_NAME = "eo_vault.bin"
INCLUDE_DIRS = ("app", "docs", "android", "scripts", "tests", "deploy", ".github")
LOADER_FILES = (
    "eo_vault_runtime.py", "vault_bootstrap.py", "scripts/eo_vault.py",
    "scripts/termux-upload-sealed.sh", "termux-eo.sh", "Dockerfile", ".dockerignore", ".gitignore",
    "docker-compose.yml", "docker-compose.turn.yml", "requirements.txt", ".env.example",
    "deploy/Caddyfile.example", "README_AR.md", "DEPLOY_AR.md", "SECURITY.md",
    "BUILD_STATUS_AR.md", "RELEASE_NOTES_AR.md", "TERMUX_UPDATE_AR.md",
    ".github/workflows/tests.yml", ".github/workflows/android-apk.yml",
)
ROOT_FILES = (
    "README_AR.md", "RELEASE_NOTES_AR.md", "SECURITY.md", "BUILD_STATUS_AR.md",
    "DEPLOY_AR.md", "TERMUX_UPDATE_AR.md", "Dockerfile", ".dockerignore",
    ".gitignore", ".env.example", "docker-compose.yml", "docker-compose.turn.yml",
    "requirements.txt", "requirements-dev.txt", "requirements-termux.txt", "VERSION",
    "eo_vault_runtime.py", "vault_bootstrap.py", "termux-eo.sh",
)
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", "data", "backups", "build", ".gradle", "vault", ".eo-vault-keys"}


def _write_secret(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit(f"Refusing to overwrite existing key file: {path}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def cmd_keygen(args: argparse.Namespace) -> None:
    project = Path(args.project_root).resolve()
    keys_dir = Path(args.keys_dir).resolve()
    if keys_dir == project or project in keys_dir.parents:
        # Keeping keys outside the project prevents accidental source control inclusion.
        raise SystemExit("Key directory must be outside the project folder.")
    master_raw = secrets.token_bytes(32)
    master_b64 = base64.urlsafe_b64encode(master_raw)
    signing = Ed25519PrivateKey.generate()
    private_pem = signing.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = signing.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    keys_dir.mkdir(parents=True, exist_ok=True)
    try:
        _write_secret(keys_dir / "EO_MASTER_KEY.b64", master_b64 + b"\n")
        _write_secret(keys_dir / "EO_INTEGRITY_SIGNING_PRIVATE.pem", private_pem)
        _write_secret(keys_dir / "EO_INTEGRITY_PUBLIC.pem", public_pem)
        os.chmod(keys_dir, 0o700)
    except Exception:
        raise
    vault_dir = project / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "trust_anchor.pub").write_bytes(public_pem)
    fingerprint = sha256(public_pem)
    runtime = project / "eo_vault_runtime.py"
    source = runtime.read_text(encoding="utf-8")
    source, replacements = re.subn(r'TRUSTED_PUBLIC_KEY_SHA256 = "[^"]+"', f'TRUSTED_PUBLIC_KEY_SHA256 = "{fingerprint}"', source, count=1)
    if replacements != 1:
        raise SystemExit("Could not update the pinned EO INTEGRITY trust anchor.")
    runtime.write_text(source, encoding="utf-8")
    print("EO VAULT keys generated.")
    print(f"Master key (keep offline/private): {keys_dir / 'EO_MASTER_KEY.b64'}")
    print(f"Integrity signing private key (never upload): {keys_dir / 'EO_INTEGRITY_SIGNING_PRIVATE.pem'}")
    print(f"Public trust anchor installed: {vault_dir / 'trust_anchor.pub'}")
    print(f"Public-key SHA-256 fingerprint: {fingerprint}")
    print("The phrase ALMANTHOMHEOOEEOOEEOO is only the scheme identifier, not the secret key.")


def collect_files(project: Path) -> list[Path]:
    candidates: set[Path] = set()
    for directory in INCLUDE_DIRS:
        base = project / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(project)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.suffix in {".pyc", ".pyo", ".class", ".apk", ".aab"}:
                continue
            candidates.add(path)
    for filename in ROOT_FILES:
        path = project / filename
        if path.is_file():
            candidates.add(path)
    if not candidates:
        raise SystemExit("No project source files were found to seal.")
    return sorted(candidates, key=lambda p: p.relative_to(project).as_posix())


def cmd_seal(args: argparse.Namespace) -> None:
    project = Path(args.project_root).resolve()
    vault_dir = Path(args.vault_dir).resolve()
    if not (project / "app" / "main.py").is_file():
        raise SystemExit("Project root does not look like ALMANTHOMH EO CN (app/main.py missing).")
    key_path = Path(args.master_key_file).resolve()
    signing_path = Path(args.signing_key_file).resolve()
    master = load_master_key(key_path.read_bytes())
    private_key = serialization.load_pem_private_key(signing_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit("Integrity signing key must be Ed25519.")
    files = collect_files(project)
    records = []
    from io import BytesIO
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(project).as_posix()
            data = path.read_bytes()
            records.append({"path": relative, "size": len(data), "sha256": sha256(data)})
            info = zipfile.ZipInfo(relative)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            archive.writestr(info, data)
    archive_bytes = buffer.getvalue()
    if len(archive_bytes) > 512 * 1024 * 1024:
        raise SystemExit("Project archive exceeds the 512 MiB sealing limit.")
    nonce = secrets.token_bytes(12)
    encrypted = MAGIC + nonce + AESGCM(master).encrypt(nonce, archive_bytes, AAD)
    vault_dir.mkdir(parents=True, exist_ok=True)
    payload_path = vault_dir / PAYLOAD_NAME
    payload_path.write_bytes(encrypted)
    payload_path.chmod(0o600)
    public_path = vault_dir / "trust_anchor.pub"
    expected_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if not public_path.is_file():
        public_path.write_bytes(expected_public)
    if public_path.read_bytes() != expected_public:
        raise SystemExit("The public trust anchor does not match the supplied signing private key. Run keygen and seal with the same key set.")
    from eo_vault_runtime import TRUSTED_PUBLIC_KEY_SHA256
    if sha256(expected_public) != TRUSTED_PUBLIC_KEY_SHA256:
        raise SystemExit("Pinned runtime trust-anchor fingerprint does not match the signing key. Run keygen with this key set before sealing.")
    loader_files = {}
    for relative in LOADER_FILES:
        path = project / relative
        # Sign every support file that is present. The complete distribution
        # requirement is enforced by cmd_package(), while isolated unit-test
        # projects intentionally contain only a minimal bootstrap fixture.
        if path.is_file():
            loader_files[relative] = sha256(path.read_bytes())
    manifest = {
        "format": "EO_VAULT",
        "version": FORMAT_VERSION,
        "product": "ALMANTHOMH EO CN V5.0.0",
        "cipher_id": CIPHER_ID,
        "cipher": CIPHER_NAME,
        "hash": HASH_NAME,
        "signature": SIGNATURE_NAME,
        "payload_file": PAYLOAD_NAME,
        "payload_size": len(encrypted),
        "payload_sha256": sha256(encrypted),
        "archive_file_count": len(records),
        "archive_size": len(archive_bytes),
        "loader_files": loader_files,
        "files": records,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    manifest_bytes = canonical_json(manifest)
    (vault_dir / "manifest.json").write_bytes(manifest_bytes)
    (vault_dir / "manifest.sig").write_bytes(private_key.sign(manifest_bytes))
    print(f"EO VAULT sealed: {len(records)} files encrypted.")
    print(f"Encrypted payload: {payload_path} ({len(encrypted)} bytes)")
    print(f"SHA-256: {sha256(encrypted)}")
    print("EO MASTER KEY and Ed25519 signing private key are not inside the vault.")


def cmd_verify(args: argparse.Namespace) -> None:
    manifest = verify_bundle(Path(args.vault_dir).resolve())
    print("EO INTEGRITY SEAL: VALID")
    print(f"Cipher: {manifest['cipher']} / {manifest['cipher_id']}")
    print(f"Payload SHA-256: {manifest['payload_sha256']}")
    print(f"Protected files: {manifest['archive_file_count']}")
    print("This verifies signature + encrypted payload digest; it does not decrypt the files.")


def cmd_open(args: argparse.Namespace) -> None:
    if args.master_key_env:
        master = os.getenv(args.master_key_env, "")
        if not master:
            raise SystemExit(f"Environment variable {args.master_key_env} is empty.")
    else:
        master = Path(args.master_key_file).read_bytes()
    destination = Path(args.destination).resolve()
    manifest = decrypt_to_directory(Path(args.vault_dir).resolve(), master, destination)
    print(f"EO VAULT decrypted after signature and {manifest['archive_file_count']} file hash checks.")
    print(f"Developer source directory: {destination}")
    print("Protect this plaintext directory; do not upload it to a public repository.")



def cmd_package(args: argparse.Namespace) -> None:
    project = Path(args.project_root).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    verify_bundle(project / "vault")
    required = [
        "vault/eo_vault.bin", "vault/manifest.json", "vault/manifest.sig", "vault/trust_anchor.pub",
        "eo_vault_runtime.py", "vault_bootstrap.py", "scripts/eo_vault.py", "termux-eo.sh", "Dockerfile", ".dockerignore", ".gitignore",
        "docker-compose.yml", "docker-compose.turn.yml", "requirements.txt", ".env.example", "deploy/Caddyfile.example",
        "README_AR.md", "DEPLOY_AR.md", "SECURITY.md", "BUILD_STATUS_AR.md",
        "RELEASE_NOTES_AR.md", "TERMUX_UPDATE_AR.md",
        "scripts/termux-upload-sealed.sh", ".github/workflows/tests.yml", ".github/workflows/android-apk.yml",
    ]
    missing = [name for name in required if not (project / name).is_file()]
    if missing:
        raise SystemExit("Cannot package sealed release; missing: " + ", ".join(missing))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in required:
            archive.write(project / name, arcname=name)
    print(f"Sealed distribution package created: {output}")
    print("Application/backend/frontend/Android/source files are inside the encrypted EO VAULT payload.")
    print("Only the minimal verified bootstrap, developer vault utility, deployment files, and documentation remain readable.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="ALMANTHOMH EO CN EO VAULT / EO MASTER KEY / EO INTEGRITY SEAL")
    sub = root.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("keygen", help="Generate separate master and Ed25519 signing keys")
    keygen.add_argument("--project-root", default=str(ROOT))
    keygen.add_argument("--keys-dir", default=str(ROOT.parent / ".eo-vault-keys"))
    keygen.set_defaults(func=cmd_keygen)
    seal = sub.add_parser("seal", help="Encrypt and sign the project source payload")
    seal.add_argument("--project-root", default=str(ROOT))
    seal.add_argument("--vault-dir", default=str(ROOT / "vault"))
    seal.add_argument("--master-key-file", required=True)
    seal.add_argument("--signing-key-file", required=True)
    seal.set_defaults(func=cmd_seal)
    verify = sub.add_parser("verify", help="Verify signature and ciphertext SHA-256")
    verify.add_argument("--vault-dir", default=str(ROOT / "vault"))
    verify.set_defaults(func=cmd_verify)
    open_cmd = sub.add_parser("open", help="Decrypt as developer after integrity verification")
    open_cmd.add_argument("--vault-dir", default=str(ROOT / "vault"))
    open_cmd.add_argument("--master-key-file")
    open_cmd.add_argument("--master-key-env")
    open_cmd.add_argument("--destination", required=True)
    open_cmd.set_defaults(func=cmd_open)
    package = sub.add_parser("package", help="Create a distribution ZIP with source code encrypted")
    package.add_argument("--project-root", default=str(ROOT))
    package.add_argument("--output", default=str(ROOT.parent / "ALMANTHOMH_EO_CN_V5.0.0_EO_VAULT.zip"))
    package.set_defaults(func=cmd_package)
    return root


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "open" and not args.master_key_file and not args.master_key_env:
        raise SystemExit("Use --master-key-file or --master-key-env.")
    args.func(args)
