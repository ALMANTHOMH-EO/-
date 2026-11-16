#!/data/data/com.termux/files/usr/bin/bash
# ALMANTHOMH EO CN - private Termux credentials + sealed upload + source editing.
# GitHub credentials are stored ONLY under Termux's private HOME, never in the repo.
set -Eeuo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$HOME/.config/almanthomh-eo-cn"
CREDENTIALS_FILE="$CONFIG_DIR/github-credentials"
ASKPASS_FILE="$CONFIG_DIR/git-askpass.sh"
KEYS_DIR="$CONFIG_DIR/eo-vault-keys"
MASTER_KEY_FILE="$KEYS_DIR/EO_MASTER_KEY.b64"
SIGNING_KEY_FILE="$KEYS_DIR/EO_INTEGRITY_SIGNING_PRIVATE.pem"
PUBLIC_KEY_FILE="$KEYS_DIR/EO_INTEGRITY_PUBLIC.pem"
DEFAULT_REPO_URL="https://github.com/ALMANTHOMH-EO/-.git"
REPO_TARGET="$HOME/projects/ALMANTHOMH_EO_CN_REPO"
SOURCE_TARGET="$HOME/projects/ALMANTHOMH_EO_CN_SOURCE_V5"
PACKAGE_NAME="ALMANTHOMH_EO_CN_V5.0.0_EO_VAULT.zip"

say() { printf '%s\n' "$*"; }
die() { say "خطأ: $*" >&2; exit 1; }
ensure_private_dir() {
  mkdir -p "$CONFIG_DIR"
  chmod 700 "$CONFIG_DIR"
  [[ ! -L "$CONFIG_DIR" ]] || die "مجلد الإعدادات رابط رمزي غير مقبول."
}
ensure_crypto() {
  command -v python >/dev/null 2>&1 || die "ثبّت Python: pkg install python"
  python -c 'import cryptography' >/dev/null 2>&1 || die "ثبّت مكتبة التحقق: pkg install python-cryptography"
}
ensure_bundle() {
  [[ -f "$ROOT/vault/manifest.json" && -f "$ROOT/vault/eo_vault.bin" ]] || die "شغّل السكربت من مجلد الحزمة المستخرجة بالكامل."
  ensure_crypto
  (cd "$ROOT" && python scripts/eo_vault.py verify)
}
valid_repo_url() {
  [[ "$1" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$ ]]
}

save_credentials() {
  ensure_private_dir
  local gh_user gh_token repo confirm temp
  read -r -p 'GitHub Username: ' gh_user
  gh_user="${gh_user//[[:space:]]/}"
  [[ "$gh_user" =~ ^[A-Za-z0-9-]+$ ]] || die "اسم مستخدم GitHub غير صالح."
  read -r -s -p 'GitHub Personal Access Token (hidden): ' gh_token
  printf '\n'
  [[ -n "$gh_token" && "$gh_token" != *$'\n'* && "$gh_token" != *$'\r'* ]] || die "التوكن فارغ أو غير صالح."
  read -r -p "Repository URL [$DEFAULT_REPO_URL]: " repo
  repo="${repo:-$DEFAULT_REPO_URL}"
  valid_repo_url "$repo" || die "استخدم رابط HTTPS لمستودع GitHub بالشكل https://github.com/OWNER/REPO.git"
  if [[ -e "$CREDENTIALS_FILE" ]]; then
    read -r -p 'يوجد اعتماد محفوظ. استبداله؟ (y/N): ' confirm
    [[ "$confirm" == "y" || "$confirm" == "Y" ]] || { say "لم يتم تغيير الاعتماد المحفوظ."; return 0; }
  fi
  temp="$(mktemp "$CONFIG_DIR/.credentials.XXXXXX")"
  printf '%s\n%s\n%s\n' "$gh_user" "$gh_token" "$repo" > "$temp"
  chmod 600 "$temp"
  mv -f "$temp" "$CREDENTIALS_FILE"
  chmod 600 "$CREDENTIALS_FILE"
  unset gh_token
  say "تم حفظ اسم المستخدم والتوكن ورابط المستودع داخل Termux الخاص."
  say "المسار: $CREDENTIALS_FILE"
  say "لن يُحفظ التوكن داخل المشروع أو رابط Git أو إعداد Git العام."
}

read_credentials() {
  [[ -f "$CREDENTIALS_FILE" && ! -L "$CREDENTIALS_FILE" ]] || return 1
  chmod 600 "$CREDENTIALS_FILE" 2>/dev/null || true
  local -a values=()
  mapfile -t values < "$CREDENTIALS_FILE"
  [[ ${#values[@]} -ge 3 ]] || return 1
  GH_USER="${values[0]}"
  GH_TOKEN="${values[1]}"
  REMOTE_URL="${values[2]}"
  [[ "$GH_USER" =~ ^[A-Za-z0-9-]+$ && -n "$GH_TOKEN" ]] || return 1
  valid_repo_url "$REMOTE_URL" || return 1
}

setup_askpass() {
  ensure_private_dir
  cat > "$ASKPASS_FILE" <<'ASKPASS'
#!/usr/bin/env sh
set -eu
: "${GH_CREDENTIALS_FILE:?}"
case "${1:-}" in
  *Username*|*username*) sed -n '1p' "$GH_CREDENTIALS_FILE" ;;
  *Password*|*password*) sed -n '2p' "$GH_CREDENTIALS_FILE" ;;
  *) exit 1 ;;
esac
ASKPASS
  chmod 700 "$ASKPASS_FILE"
  export GH_CREDENTIALS_FILE="$CREDENTIALS_FILE"
  export GIT_ASKPASS="$ASKPASS_FILE" GIT_ASKPASS_REQUIRE=force GIT_TERMINAL_PROMPT=0
}
git_run() {
  git -c credential.helper= -c core.askPass="$ASKPASS_FILE" "$@"
}

release_files() {
  RELEASE_FILES=(
    vault/eo_vault.bin vault/manifest.json vault/manifest.sig vault/trust_anchor.pub
    eo_vault_runtime.py vault_bootstrap.py scripts/eo_vault.py scripts/termux-upload-sealed.sh
    termux-eo.sh Dockerfile .dockerignore .gitignore docker-compose.yml docker-compose.turn.yml
    requirements.txt .env.example deploy/Caddyfile.example README_AR.md DEPLOY_AR.md SECURITY.md
    BUILD_STATUS_AR.md RELEASE_NOTES_AR.md TERMUX_UPDATE_AR.md
    .github/workflows/tests.yml .github/workflows/android-apk.yml
  )
}

push_release() {
  command -v git >/dev/null 2>&1 || die "ثبّت Git: pkg install git"
  ensure_bundle
  if ! read_credentials; then
    say "لا توجد بيانات GitHub محفوظة؛ أدخلها مرة واحدة الآن."
    save_credentials
    read_credentials || die "تعذر قراءة بيانات الاعتماد بعد حفظها."
  fi
  setup_askpass
  mkdir -p "$(dirname "$REPO_TARGET")"
  if [[ -d "$REPO_TARGET/.git" ]]; then
    local actual
    actual="$(git -C "$REPO_TARGET" remote get-url origin 2>/dev/null || true)"
    [[ "$actual" == "$REMOTE_URL" ]] || die "نسخة المستودع الموجودة لها origin مختلف. لم ألمسها."
  elif [[ -e "$REPO_TARGET" ]]; then
    die "مجلد هدف الرفع موجود وليس نسخة Git سليمة: $REPO_TARGET"
  else
    say "جلب المستودع إلى مجلد Termux الخاص..."
    git_run clone "$REMOTE_URL" "$REPO_TARGET"
  fi
  cd "$REPO_TARGET"
  [[ "$(git remote get-url origin)" == "$REMOTE_URL" ]] || die "رابط origin غير مطابق للمستودع المحفوظ."
  if [[ -n "$(git status --porcelain)" ]]; then
    die "نسخة المستودع بها تعديلات محلية غير محفوظة. احفظها أو راجعها أولًا: $REPO_TARGET"
  fi
  git_run fetch origin --prune
  if git show-ref --verify --quiet refs/remotes/origin/main; then
    if git show-ref --verify --quiet refs/heads/main; then git checkout main; else git checkout -b main origin/main; fi
    git merge --ff-only origin/main
  else
    if git show-ref --verify --quiet refs/heads/main; then git checkout main; else git checkout -b main; fi
  fi
  cd "$ROOT"
  release_files
  for file in "${RELEASE_FILES[@]}"; do
    [[ -f "$ROOT/$file" ]] || die "ملف توزيع ناقص: $file"
    mkdir -p "$REPO_TARGET/$(dirname "$file")"
    cp "$ROOT/$file" "$REPO_TARGET/$file"
  done
  cd "$REPO_TARGET"
  git add -f -- "${RELEASE_FILES[@]}"
  if ! git diff --cached --quiet; then
    git -c user.name="$GH_USER" -c user.email="$GH_USER@users.noreply.github.com" \
      commit -m "ALMANTHOMH EO CN V5.0.0 sealed EO VAULT release"
  else
    say "لا توجد تغييرات جديدة لرفعها."
  fi
  say "رفع ملفات EO VAULT المشفرة والموقعة فقط..."
  git_run push -u origin main
  say "اكتمل رفع ملفات التوزيع المحددة إلى main."
  say "لم يُرفع مفتاح EO MASTER KEY أو المصدر المفكوك أو بيانات GitHub السرية."
  say "أضف GitHub Actions Secret باسم EO_MASTER_KEY يدويًا قبل تشغيل التحقق والبناء."
  unset GH_TOKEN
}

install_keys() {
  local archive tmp
  archive="${1:-}"
  [[ -n "$archive" && -f "$archive" ]] || die "استخدم: bash termux-eo.sh install-keys /مسار/EO_DEVELOPER_KEYS.zip"
  ensure_crypto
  ensure_private_dir
  tmp="$(mktemp -d "$CONFIG_DIR/.keys.XXXXXX")"
  chmod 700 "$tmp"
  python - "$archive" "$tmp" <<'PY'
import sys, zipfile
from pathlib import Path
allowed = {"EO_MASTER_KEY.b64", "EO_INTEGRITY_SIGNING_PRIVATE.pem", "EO_INTEGRITY_PUBLIC.pem"}
archive, dest = Path(sys.argv[1]), Path(sys.argv[2])
with zipfile.ZipFile(archive) as zf:
    names = {Path(n).name: n for n in zf.namelist() if not n.endswith('/')}
    if not allowed.issubset(names):
        raise SystemExit("Developer key archive is missing required key files.")
    for name in allowed:
        data = zf.read(names[name])
        (dest / name).write_bytes(data)
PY
  chmod 600 "$tmp"/*
  python - "$tmp" "$ROOT/vault/trust_anchor.pub" <<'PY'
import base64, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
p = Path(sys.argv[1])
master = base64.urlsafe_b64decode((p/'EO_MASTER_KEY.b64').read_bytes().strip())
if len(master) != 32:
    raise SystemExit("EO_MASTER_KEY must decode to exactly 32 bytes.")
private = serialization.load_pem_private_key((p/'EO_INTEGRITY_SIGNING_PRIVATE.pem').read_bytes(), password=None)
public_bytes = serialization.load_pem_public_key((p/'EO_INTEGRITY_PUBLIC.pem').read_bytes()).public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
if not isinstance(private, Ed25519PrivateKey) or public_bytes != Path(sys.argv[2]).read_bytes():
    raise SystemExit("Developer signing keys do not match the release trust anchor.")
if private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo) != public_bytes:
    raise SystemExit("Developer signing private/public keys do not match.")
PY
  rm -rf "$KEYS_DIR"
  mv "$tmp" "$KEYS_DIR"
  chmod 700 "$KEYS_DIR"; chmod 600 "$KEYS_DIR"/*
  say "تم تثبيت مفاتيح المطور داخل Termux الخاص فقط: $KEYS_DIR"
  say "لا ترفع هذا المجلد إلى GitHub ولا ترسله لأي شخص."
}

open_source() {
  ensure_bundle
  [[ -f "$MASTER_KEY_FILE" && -f "$SIGNING_KEY_FILE" ]] || die "ثبّت مفاتيح المطور أولًا باستخدام install-keys."
  local destination="${1:-$SOURCE_TARGET}"
  [[ ! -e "$destination" ]] || die "مسار المصدر موجود بالفعل؛ اختر مسارًا جديدًا أو أعد تسميته: $destination"
  mkdir -p "$(dirname "$destination")"
  python "$ROOT/scripts/eo_vault.py" open --master-key-file "$MASTER_KEY_FILE" --destination "$destination"
  say "تم فك المصدر في مجلد Termux خاص. لا ترفع هذا المجلد إلى GitHub."
}

seal_source() {
  local source="${1:-$SOURCE_TARGET}"
  [[ -f "$MASTER_KEY_FILE" && -f "$SIGNING_KEY_FILE" ]] || die "مفاتيح المطور غير مثبتة."
  [[ -f "$source/app/main.py" && -f "$source/scripts/eo_vault.py" ]] || die "مجلد المصدر المفكوك غير موجود أو غير صحيح: $source"
  mkdir -p "$source/vault"
  cp "$ROOT/vault/trust_anchor.pub" "$source/vault/trust_anchor.pub"
  python "$source/scripts/eo_vault.py" seal --project-root "$source" --vault-dir "$source/vault" \
    --master-key-file "$MASTER_KEY_FILE" --signing-key-file "$SIGNING_KEY_FILE"
  python "$source/scripts/eo_vault.py" verify --vault-dir "$source/vault"
  # Sync only signed bootstrap/support files plus the new ciphertext/manifest to the outer package.
  python - "$source/vault/manifest.json" <<'PY' > "$CONFIG_DIR/loader-files.list"
import json, sys
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for name in sorted(m.get('loader_files', {})):
    print(name)
PY
  while IFS= read -r file; do
    [[ -f "$source/$file" ]] || die "ملف دعم موقّع غير موجود بعد التعديل: $file"
    mkdir -p "$ROOT/$(dirname "$file")"
    cp "$source/$file" "$ROOT/$file"
  done < "$CONFIG_DIR/loader-files.list"
  rm -rf "$ROOT/vault"
  cp -a "$source/vault" "$ROOT/vault"
  python "$ROOT/scripts/eo_vault.py" verify
  local out="$HOME/storage/downloads/$PACKAGE_NAME"
  mkdir -p "$(dirname "$out")"
  python "$ROOT/scripts/eo_vault.py" package --project-root "$ROOT" --output "$out"
  sha256sum "$out" | tee "$out.sha256"
  say "تم إنشاء حزمة مشفرة جديدة بعد التعديل: $out"
  say "شغّل: bash termux-eo.sh push لرفع النسخة الجديدة."
}

show_status() {
  if read_credentials; then
    say "GitHub user: $GH_USER"
    say "Repository: $REMOTE_URL"
    say "Token: محفوظ (لن يتم عرضه)"
    say "Credential file permissions: $(stat -c '%a' "$CREDENTIALS_FILE" 2>/dev/null || echo private)"
  else
    say "لا توجد بيانات GitHub محفوظة. استخدم: bash termux-eo.sh save"
  fi
  [[ -f "$MASTER_KEY_FILE" ]] && say "EO MASTER KEY: مثبت داخل مساحة Termux الخاصة." || say "EO MASTER KEY: غير مثبت محليًا."
  [[ -d "$SOURCE_TARGET" ]] && say "Source worktree: $SOURCE_TARGET" || say "Source worktree: لم يتم فك المصدر بعد."
}

forget_credentials() {
  if [[ -f "$CREDENTIALS_FILE" ]]; then rm -f "$CREDENTIALS_FILE"; say "تم حذف بيانات GitHub المحفوظة."; else say "لا توجد بيانات محفوظة."; fi
}

show_actions_key() {
  [[ -f "$MASTER_KEY_FILE" ]] || die "ثبّت مفاتيح المطور أولًا."
  local confirmation
  read -r -p 'لإظهار EO_MASTER_KEY لنسخه إلى GitHub Actions اكتب SHOW: ' confirmation
  [[ "$confirmation" == "SHOW" ]] || die "تم الإلغاء."
  printf 'EO_MASTER_KEY='; tr -d '\r\n' < "$MASTER_KEY_FILE"; printf '\n'
  say "لا تضع هذه القيمة في المشروع أو المحادثة أو commit."
}

usage() {
  cat <<'HELP'
ALMANTHOMH EO CN V5 - Termux helper

  bash termux-eo.sh save                         حفظ GitHub username/token مرة واحدة
  bash termux-eo.sh update-token                 إعادة إدخال واستبدال بيانات GitHub
  bash termux-eo.sh status                       عرض الحالة دون إظهار التوكن
  bash termux-eo.sh push                         التحقق ثم رفع الملفات المشفرة المحددة
  bash termux-eo.sh install-keys /path/keys.zip   تثبيت مفاتيح المطور في مساحة Termux الخاصة
  bash termux-eo.sh actions-key                  إظهار EO_MASTER_KEY بعد تأكيد صريح لنسخه إلى GitHub Secret
  bash termux-eo.sh open-source [destination]    فك المصدر للمطور داخل Termux الخاص
  bash termux-eo.sh seal-source [source-dir]     إعادة تشفير المصدر وإنتاج ZIP جديد
  bash termux-eo.sh forget                       حذف GitHub username/token المحفوظين

GitHub credentials live outside the project in ~/.config/almanthomh-eo-cn/ (mode 600).
The token is stored as a local plaintext credential protected by Termux app-private storage
and file permissions; a rooted/compromised device can still expose it. Use a fine-grained
PAT scoped only to repository Contents: Read and write + Metadata: Read.
HELP
}

COMMAND="${1:-help}"
case "$COMMAND" in
  save) save_credentials ;;
  update-token) save_credentials ;;
  status) show_status ;;
  push) push_release ;;
  install-keys) install_keys "${2:-}" ;;
  actions-key) show_actions_key ;;
  open-source) open_source "${2:-}" ;;
  seal-source) seal_source "${2:-}" ;;
  forget) forget_credentials ;;
  help|-h|--help) usage ;;
  *) usage >&2; die "أمر غير معروف: $COMMAND" ;;
esac
