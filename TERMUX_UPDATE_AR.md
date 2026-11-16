# دليل Termux — ALMANTHOMH EO CN V5.0.0

## 1) تجهيز Termux

```bash
pkg update -y
pkg install -y git python python-cryptography unzip
termux-setup-storage
```

استخرج حزمة `ALMANTHOMH_EO_CN_V5.0.0_EO_VAULT.zip` في مجلد خاص داخل Download، ثم ادخل إلى المجلد المستخرج.

## 2) حفظ اسم المستخدم والتوكن مرة واحدة

```bash
bash termux-eo.sh save
```

سيطلب GitHub Username، ثم Personal Access Token بإدخال مخفي، ثم رابط المستودع (Enter للاسم الافتراضي `https://github.com/ALMANTHOMH-EO/-.git`؛ راجع الرابط الافتراضي داخل السكربت إذا كان مستودعك مختلفًا). يحفظهما داخل:

`$HOME/.config/almanthomh-eo-cn/github-credentials`

المجلد صلاحية `700` والملف `600`. لا تحفظ الاعتمادات داخل المشروع أو `.git/config` أو رابط Git. التخزين نص واضح داخل مساحة تطبيق Termux الخاصة؛ هذا يحميه من التطبيقات العادية، لكنه لا يحميه من جهاز مخترق أو root. استخدم Fine-grained PAT محدودًا إلى Contents: Read and write وMetadata: Read للمستودع المطلوب فقط.

أوامر إدارة الاعتماد:

```bash
bash termux-eo.sh status        # يعرض اسم المستخدم دون التوكن
bash termux-eo.sh update-token  # إدخال توكن جديد
bash termux-eo.sh forget        # حذف الاعتماد المحفوظ
```

## 3) رفع الحزمة المشفرة

```bash
bash termux-eo.sh push
```

يتحقق السكربت من توقيع Ed25519 وبصمات SHA-256 قبل الرفع. يرفع قائمة محددة من الحمولة المشفرة ومشغل الإقلاع وملفات النشر والتوثيق؛ لا يرفع مجلدات المصدر المفكوك `app/` أو `docs/` أو `android/`. لا يخزن التوكن في Git ولا في سجل الأوامر. نسخة Git المحلية تحفظ في `$HOME/projects/ALMANTHOMH_EO_CN_REPO`.

## 4) تثبيت مفاتيح المطور وفك المصدر

احتفظ بملف مفاتيح المطور منفصلًا عن ZIP التوزيع، ولا ترفعه إلى GitHub. لتثبيته:

```bash
bash termux-eo.sh install-keys ~/storage/downloads/ALMANTHOMH_EO_CN_V5_DEVELOPER_KEYS.zip
```

فك المصدر للعمل المحلي:

```bash
bash termux-eo.sh open-source
```

المصدر المفكوك موجود في `$HOME/projects/ALMANTHOMH_EO_CN_SOURCE_V5` بصلاحيات خاصة. بعد تعديل الملفات، أعد التشفير والتوقيع وبناء حزمة التوزيع:

```bash
bash termux-eo.sh seal-source
```

الناتج يكتب في Download باسم `ALMANTHOMH_EO_CN_V5.0.0_EO_VAULT.zip`، كما يتم تحديث ملفات الدعم والحمولة في مجلد الحزمة الحالي. من نفس المجلد شغّل `bash termux-eo.sh push` لرفع النسخة الجديدة. لا ترفع المصدر المفكوك.

## 5) GitHub Actions Secret

بعد رفع الحزمة، ثبّت مفاتيح المطور محليًا ثم نفّذ:

```bash
bash termux-eo.sh actions-key
```

أكد `SHOW` وانسخ قيمة `EO_MASTER_KEY=` إلى GitHub → Settings → Secrets and variables → Actions باسم `EO_MASTER_KEY`. لا تلصق القيمة في Issues أو المحادثات أو ملفات المشروع.

لبناء APK Release موقع، أضف كذلك أسرار keystore الأربعة الموضحة في `README_AR.md`. دونها ينتج workflow ملف Debug فقط.

## 6) ما لا يفعله الرفع

رفع الملفات إلى GitHub لا ينشر FastAPI أو PostgreSQL أو TURN. يلزم VPS/Docker ونطاق HTTPS وقاعدة PostgreSQL وإعداد الأسرار. كما أن بناء APK الفعلي يحدث في GitHub Actions بعد إضافة `EO_MASTER_KEY`، ولم يتم اختبار جهاز حقيقي أو بث حقيقي بمجرد نجاح الرفع.
