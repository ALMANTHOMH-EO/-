#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/storage/downloads/ALMANTHOMH_EO_CN_V1"
if [[ ! -d "$TARGET_DIR/.git" ]]; then
  echo "لم أجد مجلد V1 القديم هنا: $TARGET_DIR"
  echo "انقل مجلد V1 إلى Downloads مع الاحتفاظ بمجلد .git ثم أعد المحاولة."
  exit 1
fi
EXPECTED_REMOTE="https://github.com/ALMANTHOMH-EO/-.git"
ACTUAL_REMOTE="$(git -C "$TARGET_DIR" remote get-url origin 2>/dev/null || true)"
if [[ "$ACTUAL_REMOTE" != "$EXPECTED_REMOTE" ]]; then
  echo "توقف للحماية: origin في مجلد V1 ليس المستودع المتوقع."
  echo "الموجود: ${ACTUAL_REMOTE:-لا يوجد origin}"
  exit 1
fi
# Preserve the existing .git history; only replace project files.
cp -r "$SOURCE_DIR"/. "$TARGET_DIR"/
git config --global --add safe.directory "$TARGET_DIR" 2>/dev/null || true
chmod 700 "$TARGET_DIR/scripts/termux-push-update.sh" 2>/dev/null || true
cd "$TARGET_DIR"
echo "تم نسخ ملفات V2 مع الحفاظ على سجل Git القديم."
bash scripts/termux-push-update.sh
