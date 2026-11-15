#!/usr/bin/env python3
"""Create the first ALMANTHOMH EO CN administrator without writing secrets to disk."""
import getpass
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

base = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
key = getpass.getpass("ADMIN_BOOTSTRAP_KEY (hidden): ")
username = input("Admin username (3-24 lowercase characters): ").strip().lower()
display_name = input("Display name: ").strip()
age_band = input("Age band (under18 / 18plus): ").strip()
password = getpass.getpass("New admin password (12+ characters): ")
confirm = getpass.getpass("Repeat password: ")
if password != confirm:
    sys.exit("Passwords did not match.")
if len(password) < 12:
    sys.exit("Password must be at least 12 characters.")

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def request(path, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with opener.open(req, timeout=20) as res:
        return json.loads(res.read().decode("utf-8"))

try:
    csrf = request("/api/auth/csrf")["csrfToken"]
    result = request("/api/admin/bootstrap", "POST", {
        "username": username, "display_name": display_name,
        "age_band": age_band, "password": password,
    }, {"X-CSRF-Token": csrf, "X-Bootstrap-Key": key})
    print(result.get("message", "Admin created."))
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", "replace")
    sys.exit(f"Bootstrap failed (HTTP {exc.code}): {body}")
except Exception as exc:
    sys.exit(f"Bootstrap failed: {exc}")
finally:
    key = password = confirm = ""
