# دليل تشغيل ونشر ALMANTHOMH EO CN V2.0.0

## أ. تشغيل محلي عبر Docker

المتطلبات: Docker Engine وDocker Compose plugin.

```bash
cp .env.example .env
```

افتح `.env` واكتب قيمتين مختلفتين وعشوائيتين طويلتين. يمكن إنشاء قيم hex عشوائية بواسطة:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

الأولى لـ `POSTGRES_PASSWORD` والثانية لـ `ADMIN_BOOTSTRAP_KEY`. لا تستخدم نفس القيمة للاثنين.

ثم شغّل:

```bash
docker compose up -d --build
docker compose ps
```

افتح `http://localhost:8000`. فحص الخادم:

```bash
curl http://localhost:8000/api/health
```

## ب. إنشاء المدير الأول

على جهاز يستطيع الوصول إلى الخادم، وبعد ضبط متغير البيئة `ADMIN_BOOTSTRAP_KEY` بالقيمة الموجودة على الخادم، شغّل:

```bash
python -m pip install -r requirements.txt
python scripts/bootstrap_admin.py
```

سيطلب السكربت المفتاح وكلمة المرور بشكل مخفي. اختَر اسم مستخدم إنجليزيًا وكلمة مرور قوية لا تقل عن 12 حرفًا. بعد ظهور نجاح الإنشاء، احذف `ADMIN_BOOTSTRAP_KEY` من إعدادات الخادم وأعد تشغيله. نقطة التأسيس لا تسمح بإنشاء مدير ثانٍ.

عند النشر على خادم بعيد، مرر عنوانه قبل تشغيل السكربت:

```bash
BASE_URL=https://YOUR-DOMAIN.example python scripts/bootstrap_admin.py
```

لا تضع قيمة المفتاح نفسها في الأمر أو سجل الأوامر؛ السكربت سيطلبها مخفيًا.

## ج. تشغيل مباشر دون Docker (للتجربة فقط)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COOKIE_SECURE=false
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

قاعدة SQLite ستنشأ في `data/alm_events.db`. لا تستخدم SQLite على أكثر من نسخة خادم متزامنة، ولا تضع ملف قاعدة البيانات داخل مجلد يُمسح عند إعادة النشر.

## د. النشر العام

GitHub Pages لا يشغّل Python ولا PostgreSQL. يلزم نشر هذا المشروع كحاوية Docker في خدمة استضافة تدعم تشغيل Docker، مع قاعدة PostgreSQL دائمة ونسخ احتياطي. اضبط متغيرات الخدمة:

- `DATABASE_URL`: عنوان PostgreSQL بصيغة `postgresql+psycopg://...`.
- `COOKIE_SECURE=true`.
- `ADMIN_BOOTSTRAP_KEY`: قيمة مؤقتة عشوائية تُحذف بعد تأسيس المدير.

اجعل الوكيل العكسي يمرر HTTPS إلى التطبيق، وانشر الواجهة والخادم على نفس النطاق. لا توجّه GitHub Pages إلى الخادم على أنه API يعمل تلقائيًا. بعد نجاح نشر Docker على نطاقك، استخدم ذلك النطاق بدل رابط `github.io`.

## هـ. التحقق بعد النشر

```bash
curl https://YOUR-DOMAIN.example/api/health
```

المتوقع JSON يحوي `ok: true` و`database: "connected"`. أنشئ حسابًا عاديًا، سجّل الدخول، جرّب حجز خانة ثم تحريرها من حساب آخر للتأكد من منع الحجز المزدوج.

## و. حدود الخدمة

- مدة الخمول 14 يومًا، مع تنبيه واجهة في اليوم 10 و13.
- حد الاستخدام 6 ساعات يوميًا للمستخدم العادي بتوقيت القاهرة (حساب المطور غير محدود) (يعتمد على نبضات الصفحة المرئية؛ ليس مراقبة لنشاط الهاتف كله).
- رموز الربط صالحة 15 دقيقة وتُستخدم مرة واحدة.
- لا يوجد بث شاشة أو تحكم عن بعد أو APK في هذا الإصدار.

## ز. تجربة محلية على Termux (ليست نشرًا عامًا)

انسخ المشروع إلى مجلدك في Termux، وثبّت Python ثم شغّل:

```bash
pkg update -y
pkg install -y python
export COOKIE_SECURE=false
export ADMIN_BOOTSTRAP_KEY='ضع-قيمة-عشوائية-طويلة-مؤقتة-هنا'
bash scripts/run-termux.sh
```

افتح متصفح الهاتف على `http://127.0.0.1:8000`. تبقى الخدمة محلية على الهاتف ولا تجعل الموقع متاحًا للناس عبر الإنترنت. لإيقاف الخادم اضغط Ctrl+C داخل جلسة Termux.
