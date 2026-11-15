# تحديث المستودع الحالي من Termux دون فقد سجل Git

1. نزّل وفك ضغط `ALMANTHOMH_EO_CN_V2.0.0.zip` في Downloads.
2. تأكد أن مجلد V1 القديم ما زال في `~/storage/downloads/ALMANTHOMH_EO_CN_V1` وأن بداخله `.git`.
3. من مجلد V2 شغّل أمرًا واحدًا:

```bash
cd ~/storage/downloads/ALMANTHOMH_EO_CN_V2
bash scripts/install-and-push-termux.sh
```

السكريبت ينسخ الملفات الجديدة إلى V1 مع الحفاظ على `.git`، ويتحقق من رابط origin، ثم يطلب اسم مستخدم GitHub والتوكن المخفي ويرفع التحديث. لا تنفّذ `git init` ولا تحذف `.git` ولا ترسل التوكن في المحادثة.

5. بعد نجاح Push، انتبه: GitHub Pages لا يشغّل الخادم. تشغيل الحسابات والحجوزات يحتاج نشر Docker/PostgreSQL حسب `DEPLOY_AR.md`.
