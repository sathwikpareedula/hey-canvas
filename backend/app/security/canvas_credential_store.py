"""Optional Windows DPAPI storage for Canvas API tokens (user-scoped)."""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import SecretStr

_STORE_VERSION = 1
_STORE_ENV = "HEY_CANVAS_CREDENTIAL_STORE"

LiteralStorage = Literal["dpapi", "none", "unavailable"]


@dataclass(frozen=True)
class CredentialStoreStatus:
    available: bool
    has_token: bool
    storage: LiteralStorage


def _default_store_path() -> Path:
    override = os.environ.get(_STORE_ENV)
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "HeyCanvas" / "canvas-credential.json"
    return Path.home() / ".hey-canvas" / "canvas-credential.json"


def _dpapi_encrypt(plain: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptProtectData.argtypes = (
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPCWSTR,
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        )
        crypt32.CryptProtectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
        kernel32.LocalFree.restype = wintypes.HLOCAL

        def _blob_from_bytes(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_char]]:
            buffer = ctypes.create_string_buffer(data, len(data))
            blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
            return blob, buffer

        in_blob, input_buffer = _blob_from_bytes(plain)
        out_blob = DATA_BLOB()
        try:
            if not crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                return None
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.memset(input_buffer, 0, len(input_buffer))
            if out_blob.pbData:
                kernel32.LocalFree(ctypes.cast(out_blob.pbData, wintypes.HLOCAL))
    except Exception:
        return None


def _dpapi_decrypt(cipher: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptUnprotectData.argtypes = (
            ctypes.POINTER(DATA_BLOB),
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(DATA_BLOB),
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(DATA_BLOB),
        )
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = (wintypes.HLOCAL,)
        kernel32.LocalFree.restype = wintypes.HLOCAL

        def _blob_from_bytes(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_char]]:
            buffer = ctypes.create_string_buffer(data, len(data))
            blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
            return blob, buffer

        in_blob, input_buffer = _blob_from_bytes(cipher)
        out_blob = DATA_BLOB()
        try:
            if not crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(out_blob),
            ):
                return None
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            # The DPAPI output is plaintext. Wipe it before releasing the
            # LocalAlloc buffer, even when copying/decoding later fails.
            if out_blob.pbData:
                ctypes.memset(out_blob.pbData, 0, out_blob.cbData)
                kernel32.LocalFree(ctypes.cast(out_blob.pbData, wintypes.HLOCAL))
            # The encrypted input is not secret plaintext, but clear the
            # temporary native buffer for consistent bounded lifetimes.
            ctypes.memset(input_buffer, 0, len(input_buffer))
    except Exception:
        return None


def store_status() -> CredentialStoreStatus:
    path = _default_store_path()
    storage: LiteralStorage = "dpapi" if sys.platform == "win32" else "unavailable"
    if not path.is_file():
        return CredentialStoreStatus(
            available=sys.platform == "win32",
            has_token=False,
            storage=storage,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        has = bool(payload.get("ciphertext_b64"))
        return CredentialStoreStatus(
            available=sys.platform == "win32",
            has_token=has,
            storage="dpapi" if has else "none",
        )
    except Exception:
        return CredentialStoreStatus(available=False, has_token=False, storage="none")


def load_stored_canvas_token() -> SecretStr | None:
    path = _default_store_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != _STORE_VERSION:
            return None
        cipher = base64.b64decode(payload["ciphertext_b64"])
        plain = _dpapi_decrypt(cipher)
        if not plain:
            return None
        token = plain.decode("utf-8").strip()
        return SecretStr(token) if token else None
    except Exception:
        return None


def save_canvas_token(token: str) -> bool:
    """Persist token with DPAPI. Returns False when OS storage is unavailable."""
    trimmed = token.strip()
    if not trimmed:
        return False
    encrypted = _dpapi_encrypt(trimmed.encode("utf-8"))
    if encrypted is None:
        return False
    path = _default_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _STORE_VERSION,
        "ciphertext_b64": base64.b64encode(encrypted).decode("ascii"),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return True


def migrate_env_token_to_store(env_token: SecretStr | None) -> bool:
    """Copy env token into DPAPI when store is empty (does not remove .env)."""
    if env_token is None or store_status().has_token:
        return False
    return save_canvas_token(env_token.get_secret_value())
