"""EO VAULT runtime verification and decryption primitives.

The public verification key is pinned here. The private signing key and AES master
key must remain outside the repository and release archive.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature

CIPHER_ID = "ALMANTHOMHEOOEEOOEEOO"
CIPHER_NAME = "AES-256-GCM"
SIGNATURE_NAME = "Ed25519"
HASH_NAME = "SHA-256"
FORMAT_VERSION = 1
MAGIC = b"EOVLT1\x00"
AAD = f"{CIPHER_ID}|EO_VAULT|v{FORMAT_VERSION}".encode("ascii")
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_FILES = 12000
MAX_TOTAL_UNCOMPRESSED = 768 * 1024 * 1024
MAX_SINGLE_FILE = 128 * 1024 * 1024

# Replaced by scripts/eo_vault.py keygen. This is a public trust anchor, not a secret.
TRUSTED_PUBLIC_KEY_SHA256 = "ee2d3949b5ed16ebe35a2d6022d248a67d11ff405df8f07b4f0e2e3763202063"


class VaultError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_master_key(value: str | bytes) -> bytes:
    if isinstance(value, str):
        candidate = value.strip().encode("ascii")
    else:
        candidate = value.strip()
    try:
        decoded = base64.urlsafe_b64decode(candidate + b"=" * (-len(candidate) % 4))
    except Exception as exc:
        raise VaultError("EO_MASTER_KEY is not valid URL-safe Base64.") from exc
    if len(decoded) != 32:
        raise VaultError("EO_MASTER_KEY must decode to exactly 32 bytes.")
    return decoded


def _safe_member_name(name: str) -> str:
    if not name or "\\" in name or "\x00" in name:
        raise VaultError(f"Unsafe archive member: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise VaultError(f"Unsafe archive member: {name!r}")
    if len(path.parts) > 20:
        raise VaultError("Archive path is too deep.")
    return path.as_posix()


def _read_and_verify_manifest(vault_dir: Path) -> dict[str, Any]:
    vault_dir = Path(vault_dir)
    manifest_path = vault_dir / "manifest.json"
    signature_path = vault_dir / "manifest.sig"
    public_key_path = vault_dir / "trust_anchor.pub"
    for path in (manifest_path, signature_path, public_key_path):
        if not path.is_file():
            raise VaultError(f"Missing integrity metadata: {path.name}")
    public_pem = public_key_path.read_bytes()
    actual_anchor_hash = sha256(public_pem)
    if TRUSTED_PUBLIC_KEY_SHA256.startswith("__") or actual_anchor_hash != TRUSTED_PUBLIC_KEY_SHA256:
        raise VaultError("EO INTEGRITY SEAL trust-anchor fingerprint mismatch.")
    public_key = load_pem_public_key(public_pem)
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VaultError("Integrity manifest is not valid JSON.") from exc
    if canonical_json(manifest) != manifest_bytes:
        raise VaultError("Integrity manifest is not in canonical form.")
    if manifest.get("format") != "EO_VAULT" or manifest.get("version") != FORMAT_VERSION:
        raise VaultError("Unsupported EO VAULT manifest format.")
    if manifest.get("cipher_id") != CIPHER_ID or manifest.get("cipher") != CIPHER_NAME:
        raise VaultError("Unexpected EO VAULT cipher identifier or algorithm.")
    try:
        public_key.verify(signature_path.read_bytes(), manifest_bytes)
    except InvalidSignature as exc:
        raise VaultError("EO INTEGRITY SEAL signature is invalid; manifest may be altered.") from exc
    except Exception as exc:
        raise VaultError("EO INTEGRITY SEAL signature cannot be verified.") from exc

    # Verify the plaintext bootstrap/support files too (where they are present).
    for relative, expected_hash in manifest.get("loader_files", {}).items():
        support_path = vault_dir.parent / _safe_member_name(relative)
        if not support_path.is_file() or sha256(support_path.read_bytes()) != expected_hash:
            raise VaultError(f"EO INTEGRITY SEAL mismatch in support file: {relative}")
    return manifest


def verify_bundle(vault_dir: Path) -> dict[str, Any]:
    """Verify signature + encrypted payload digest without needing the master key."""
    vault_dir = Path(vault_dir)
    manifest = _read_and_verify_manifest(vault_dir)
    payload_name = _safe_member_name(manifest["payload_file"])
    payload_path = vault_dir / payload_name
    if not payload_path.is_file():
        raise VaultError("Encrypted EO VAULT payload is missing.")
    payload = payload_path.read_bytes()
    if len(payload) > MAX_ARCHIVE_BYTES or len(payload) != int(manifest["payload_size"]):
        raise VaultError("Encrypted EO VAULT payload size mismatch or limit exceeded.")
    if sha256(payload) != manifest["payload_sha256"]:
        raise VaultError("EO INTEGRITY SEAL SHA-256 mismatch in encrypted payload.")
    return manifest


def decrypt_payload(vault_dir: Path, master_key: str | bytes) -> tuple[dict[str, Any], bytes]:
    manifest = verify_bundle(vault_dir)
    payload_path = Path(vault_dir) / manifest["payload_file"]
    blob = payload_path.read_bytes()
    if not blob.startswith(MAGIC) or len(blob) <= len(MAGIC) + 12 + 16:
        raise VaultError("EO VAULT payload header is invalid.")
    nonce_start = len(MAGIC)
    nonce = blob[nonce_start:nonce_start + 12]
    ciphertext = blob[nonce_start + 12:]
    try:
        archive_bytes = AESGCM(load_master_key(master_key)).decrypt(nonce, ciphertext, AAD)
    except Exception as exc:
        raise VaultError("EO MASTER KEY is incorrect or encrypted payload authentication failed.") from exc
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise VaultError("Decrypted archive exceeds configured size limit.")
    return manifest, archive_bytes


def verify_archive_members(manifest: dict[str, Any], archive_bytes: bytes) -> dict[str, bytes]:
    expected = manifest.get("files")
    if not isinstance(expected, list) or len(expected) > MAX_FILES:
        raise VaultError("Manifest file list is invalid or too large.")
    expected_map: dict[str, dict[str, Any]] = {}
    for record in expected:
        name = _safe_member_name(str(record.get("path", "")))
        if name in expected_map:
            raise VaultError(f"Duplicate file path in manifest: {name}")
        expected_map[name] = record
    result: dict[str, bytes] = {}
    total = 0
    try:
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(archive_bytes), "r") as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) != len(expected_map) or len(members) > MAX_FILES:
                raise VaultError("EO VAULT archive file count does not match its manifest.")
            for info in members:
                name = _safe_member_name(info.filename)
                record = expected_map.get(name)
                if record is None:
                    raise VaultError(f"Unlisted file inside EO VAULT archive: {name}")
                # Reject symlinks and suspicious compression ratios.
                mode = (info.external_attr >> 16) & 0xFFFF
                if (mode & 0o170000) == 0o120000:
                    raise VaultError(f"Symbolic links are not allowed in EO VAULT: {name}")
                if info.file_size > MAX_SINGLE_FILE:
                    raise VaultError(f"File exceeds EO VAULT per-file limit: {name}")
                total += info.file_size
                if total > MAX_TOTAL_UNCOMPRESSED:
                    raise VaultError("EO VAULT archive expands beyond the configured limit.")
                data = archive.read(info)
                if len(data) != int(record["size"]) or sha256(data) != record["sha256"]:
                    raise VaultError(f"EO INTEGRITY SEAL SHA-256 mismatch: {name}")
                result[name] = data
    except zipfile.BadZipFile as exc:
        raise VaultError("Decrypted EO VAULT archive is not a valid ZIP.") from exc
    if set(result) != set(expected_map):
        raise VaultError("EO VAULT archive is incomplete.")
    return result


def decrypt_to_directory(vault_dir: Path, master_key: str | bytes, destination: Path) -> dict[str, Any]:
    manifest, archive_bytes = decrypt_payload(vault_dir, master_key)
    files = verify_archive_members(manifest, archive_bytes)
    destination = Path(destination).resolve()
    if destination.exists() and any(destination.iterdir()):
        raise VaultError("Destination must be empty before EO VAULT extraction.")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        for name, data in files.items():
            target = (destination / name).resolve()
            if destination not in target.parents:
                raise VaultError(f"Extraction path escapes destination: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            try:
                target.chmod(0o600)
            except OSError:
                pass
        for directory in sorted((p for p in destination.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                directory.chmod(0o700)
            except OSError:
                pass
        try:
            destination.chmod(0o700)
        except OSError:
            pass
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return manifest
