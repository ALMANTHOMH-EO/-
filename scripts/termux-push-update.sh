#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: هذا المجلد لا يحتوي على سجل Git. انسخ ملفات V2 إلى مجلد V1 الذي يحتوي على .git أولًا."
  exit 1
fi
REMOTE_URL="https://github.com/ALMANTHOMH-EO/-.git"
if ! git remote get-url origin >/dev/null 2>&1; then git remote add origin "$REMOTE_URL"; fi
CURRENT_REMOTE="$(git remote get-url origin)"
if [[ "$CURRENT_REMOTE" != "$REMOTE_URL" ]]; then
  echo "ERROR: origin الحالي مختلف: $CURRENT_REMOTE"
  echo "راجع المستودع قبل الاستبدال؛ لم يتم تعديل remote."
  exit 1
fi
read -r -p 'GitHub Username: ' GH_USER
GH_USER="${GH_USER//[[:space:]]/}"
if [[ -z "$GH_USER" || ! "$GH_USER" =~ ^[A-Za-z0-9-]+$ ]]; then echo "اسم المستخدم غير صالح"; exit 1; fi
read -r -s -p 'GitHub Token (hidden): ' GH_TOKEN
printf '\n'
if [[ -z "$GH_TOKEN" ]]; then echo "لم يتم إدخال Token"; exit 1; fi
ASKPASS_FILE="$(mktemp)"
cleanup() { unset GH_TOKEN 2>/dev/null || true; rm -f "$ASKPASS_FILE"; }
trap cleanup EXIT INT TERM
cat > "$ASKPASS_FILE" <<'ASKPASS'
#!/data/data/com.termux/files/usr/bin/sh
case "$1" in
  *Username*) printf '%s\n' "$GH_USER" ;;
  *Password*) printf '%s\n' "$GH_TOKEN" ;;
  *) printf '\n' ;;
esac
ASKPASS
chmod 700 "$ASKPASS_FILE"
export GH_USER GH_TOKEN GIT_ASKPASS="$ASKPASS_FILE" GIT_TERMINAL_PROMPT=0

git add -A
if ! git diff --cached --quiet; then
  git commit -m "ALMANTHOMH EO CN v2.0.0 full-stack application"
else
  echo "لا توجد تغييرات جديدة للالتزام بها."
fi
BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then echo "تعذر تحديد الفرع الحالي"; exit 1; fi
printf '\nرفع الفرع %s إلى GitHub...\n' "$BRANCH"
git -c credential.helper= push -u origin "$BRANCH"
printf '\nتم رفع تحديث V2.0.0 بنجاح.\n'
