#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ ! -f "docs/index.html" || ! -f "README_AR.md" ]]; then
  echo "ERROR: شغّل السكربت من حزمة ALMANTHOMH_EO_CN_V1 الأصلية."
  exit 1
fi

for bin in git curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "الأداة $bin غير مثبتة."
    if command -v pkg >/dev/null 2>&1; then
      pkg install -y "$bin"
    else
      echo "ثبّت $bin ثم أعد تشغيل السكربت."
      exit 1
    fi
  fi
done

clear 2>/dev/null || true
printf '\n====================================================\n'
printf '       ALMANTHOMH EO CN — TERMUX UPLOADER V1.0\n'
printf '====================================================\n\n'
printf 'سيطلب السكربت اسم مستخدم GitHub ثم التوكن بشكل مخفي.\n'
printf 'لن يحفظ التوكن داخل ملفات المشروع أو إعداد Git.\n\n'

read -r -p 'GitHub Username: ' GH_USER
GH_USER="${GH_USER//[[:space:]]/}"
if [[ -z "$GH_USER" || ! "$GH_USER" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "ERROR: اسم مستخدم GitHub غير صالح."
  exit 1
fi

read -r -s -p 'GitHub Token (hidden): ' GH_TOKEN
printf '\n'
if [[ -z "$GH_TOKEN" ]]; then
  echo "ERROR: لم يتم إدخال توكن."
  exit 1
fi

DEFAULT_REPO="-"
read -r -p "Repository name [${DEFAULT_REPO}]: " REPO_NAME
REPO_NAME="${REPO_NAME:-$DEFAULT_REPO}"
if [[ ! "$REPO_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: اسم المستودع غير صالح."
  unset GH_TOKEN
  exit 1
fi

read -r -p 'Repository owner [ALMANTHOMH-EO]: ' REPO_OWNER
REPO_OWNER="${REPO_OWNER:-ALMANTHOMH-EO}"
if [[ ! "$REPO_OWNER" =~ ^[A-Za-z0-9-]+$ ]]; then
  echo "ERROR: اسم مالك المستودع غير صالح."
  unset GH_TOKEN
  exit 1
fi
OWNER_REPO="${REPO_OWNER}/${REPO_NAME}"
REMOTE_URL="https://github.com/${OWNER_REPO}.git"
ASKPASS_FILE="$(mktemp)"
CURL_CONFIG="$(mktemp)"
API_BODY="$(mktemp)"
cleanup() {
  unset GH_TOKEN 2>/dev/null || true
  rm -f "$ASKPASS_FILE" "$CURL_CONFIG" "$API_BODY"
}
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
export GH_USER GH_TOKEN
export GIT_ASKPASS="$ASKPASS_FILE"
export GIT_TERMINAL_PROMPT=0

# curl reads the authorization header from a private temporary config file,
# so the token is not placed directly in curl's argument list.
printf 'header = "Accept: application/vnd.github+json"\n' > "$CURL_CONFIG"
printf 'header = "X-GitHub-Api-Version: 2022-11-28"\n' >> "$CURL_CONFIG"
printf 'header = "Authorization: Bearer %s"\n' "$GH_TOKEN" >> "$CURL_CONFIG"
chmod 600 "$CURL_CONFIG"

printf '\n[1/5] التحقق من المستودع وصلاحية قراءة بياناته...\n'
HTTP_CODE="$(curl --config "$CURL_CONFIG" -sS -o "$API_BODY" -w '%{http_code}' "https://api.github.com/repos/${OWNER_REPO}")"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "ERROR: المستودع غير موجود أو لا يمكن الوصول إليه (HTTP $HTTP_CODE)."
  echo "أنشئ مستودعًا فارغًا على GitHub بهذا الاسم ثم أعد التشغيل."
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -b main
fi
if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REMOTE_URL"
else
  CURRENT_REMOTE="$(git remote get-url origin)"
  if [[ "$CURRENT_REMOTE" != "$REMOTE_URL" ]]; then
    git remote set-url origin "$REMOTE_URL"
  fi
fi

printf '[3/5] تجهيز ملفات الإصدار...\n'
git config user.name "${GH_USER}"
git config user.email "${GH_USER}@users.noreply.github.com"
git add -A
if ! git diff --cached --quiet; then
  git commit -m "ALMANTHOMH EO CN v1.0.0 initial release"
else
  echo "لا توجد تغييرات جديدة لإضافتها؛ سيتم رفع الالتزام الحالي إن وجد."
fi

printf '[4/5] فحص الفروع البعيدة لتجنب الكتابة فوق ملفات موجودة...\n'
REMOTE_BRANCHES="$(GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote --heads origin 2>/dev/null || true)"
if printf '%s' "$REMOTE_BRANCHES" | grep -q 'refs/heads/main$'; then
  TARGET_BRANCH="alm-eo-cn-v1-$(date +%Y%m%d%H%M%S)"
  git checkout -B "$TARGET_BRANCH"
  echo "وجدنا فرع main موجودًا؛ سنرفع الإصدار إلى فرع جديد دون استبدال ملفاتك الحالية."
else
  TARGET_BRANCH="main"
  git checkout -B main
fi

printf '[5/5] رفع الإصدار إلى GitHub...\n'
GIT_TERMINAL_PROMPT=0 git -c credential.helper= push -u origin "$TARGET_BRANCH"

printf '\n====================================================\n'
printf 'تم رفع ملفات الإصدار بنجاح.\n'
printf 'Repository: %s\n' "$OWNER_REPO"
printf 'Branch: %s\n' "$TARGET_BRANCH"
printf 'Files: docs/ (GitHub Pages source)\n'
printf '====================================================\n\n'
printf 'الخطوة التالية: GitHub → Settings → Pages → Deploy from a branch.\n'
printf 'اختر الفرع %s والمجلد /docs ثم Save.\n' "$TARGET_BRANCH"
printf 'تنبيه: لم يتم نشر APK؛ تطبيق Android المرافق لم يُبنَ بعد.\n'
