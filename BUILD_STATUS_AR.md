# حالة مصدر ALMANTHOMH EO CN V5.0.0 — EAGLE NEXUS

## وظائف مؤكدة في المصدر

- FastAPI مع SQLite للاختبار وPostgreSQL للإنتاج، وترحيل إضافي للجداول الجديدة.
- حسابات المستخدمين وكلمات مرور مخزنة كـPBKDF2 hashes، وجلسات آمنة وCSRF ومحددات مستقلة لمحاولات الدخول والأكواد.
- TOTP من 6 أرقام، أسراره مشفرة في قاعدة البيانات. بعد تفعيلها تصبح مطلوبة عند كل تسجيل دخول جديد، وعند تفعيل كود الاستخدام وفتح غرفة الاسترداد.
- حد الاستخدام اليومي: ساعتان أساسيًا، 6 ساعات بكود المستخدم، وحتى 24 ساعة بكود المطور. كود المطور لا يمنح دور ADMIN.
- كود الاستحقاق الخاطئ لا يزيد عداد TOTP، لكنه يبقى محميًا بمحدد إساءة استخدام مستقل. غرفة الاسترداد لها محدد منفصل كذلك.
- قفل TOTP: أول 3 أخطاء = 10 دقائق؛ ثم كل خطأين إضافيين يضاعفان المدة (20، 40، 80...) حتى 48 ساعة.
- عند بلوغ قفل TOTP مدة 48 ساعة: تسجيل خروج جميع جلسات الحساب، تحرير خانة الهاتف والكمبيوتر، إبطال pairing codes واعتمادات Android، وإنهاء جلسات المشاهدة. هذا soft reset لخانات المنظومة فقط؛ لا يعيد تشغيل الهاتف أو يمسح ملفاته.
- تسجيل أحداث تسجيل الدخول ومحاولات TOTP وأكواد الاستحقاق وفتح غرفة الاسترداد وتدوير مفاتيح الخانات وإعادة الضبط داخل `security_events`؛ تعرض غرفة المطور السجل مع تحميل صفحات أقدم.
- 300 خانة هاتف في 6 مجموعات × 50، و50 خانة كمبيوتر مستقلة.
- غرفة الاسترداد تتطلب ADMIN + TOTP + مفتاحًا منفصلًا مضبوطًا عبر `EMERGENCY_VAULT_CODE_HASH`.
- لكل خانة مفتاح استرداد مختلف أحادي الاستخدام. زر غرفة المطور يولد المفاتيح الناقصة للخانات الـ350 دفعة واحدة أو يسمح بتدوير خانة مفردة. يظهر الرمز مرة واحدة فقط، وتخزن قاعدة البيانات SHA-256 digest لا النص الأصلي.
- مفتاح الخانة لا يكشف كلمة مرور الحساب ولا يسمح بانتحال المستخدم؛ يحرر الخانة ويلغي اعتمادها وجلساتها المرتبطة. يلزم دخول الحساب الأصلي لإعادة الحجز.
- `scripts/generate-emergency-vault-code.py` ينشئ مفتاح غرفة جديدًا ويحفظ بصمته في `.env`، ويرفض الاستبدال دون `--rotate`. لا تستخدم رمزًا سبق مشاركته في محادثة.
- `scripts/generate-developer-access-code.py` ينشئ كود مطور عشوائيًا، يخزن البصمة فقط، ويرفض تدوير كود موجود دون `--rotate`.
- واجهة موقع/PWA متجاوبة، صورة ESKO الجديدة كخلفية للموقع وAndroid، أيقونة نسر، مقدمة CSS، وأصوات نقر اختيارية.
- تطبيق Android مصدر Kotlin/Gradle، مشاركة شاشة MediaProjection بموافقة صريحة وإشعار مستمر، وربط برمز مؤقت.
- جلسة Android مستقلة قبل الربط: تسجيل دخول بكلمة المرور وTOTP عند تفعيلها، Bearer token عشوائي مخزن كبصمة في الخادم ومشفّر محليًا عبر Android Keystore، نبضات استخدام واستحقاق وتسجيل خروج مستقل. تفعيل الكود أول مرة من التطبيق يصدر جلسة تطبيق ولا يضع كلمة المرور في التخزين المحلي.

## مساحة المستخدم ومديرو المجموعات

- CRUD للملاحظات والمهام، تفضيلات المستخدم، الإشعارات، قواعد الأتمتة المحدودة، وطلبات الدعم محفوظة في قاعدة البيانات ومربوطة بمالك السجل.
- تقارير الخصوصية والتشخيص والخط الزمني وتصدير/استيراد بيانات مساحة العمل؛ لا يتم استيراد جلسات أو رموز أو مفاتيح أجهزة.
- قفل الطوارئ وحذف الحساب يتطلبان إعادة تحقق؛ قفل الطوارئ يلغي الجلسات والربط واعتمادات الأجهزة والخانات الأخرى.
- دور `group_manager` يقتصر على مجموعة هاتف واحدة من الست؛ يمنع الوصول إلى المجموعات الأخرى والكمبيوتر، ويستطيع المدير تعيين الدور أو إزالته.
- هذه الخدمات تمثل نواة عملية لمساحة المستخدم، ولا تعني أن كل الأفكار الاسمية الـ119 السابقة تحولت إلى منتجات مستقلة؛ أي وحدة غير مذكورة بوصفها منفذة تظل خارج نطاق التنفيذ المؤكد.

## نتائج الاختبار الحالية

- `pytest -q`: **36 اختبارًا ناجحًا**. يشمل اختبار جلسة Android قبل ربط الجهاز، ورفض الدخول دون TOTP للحساب المحمي، واحتساب النبضات ضمن نفس رصيد الحساب، وإبطال الجلسة بعد تسجيل الخروج. تشمل تدفق TOTP 10/20/40 دقيقة، والوصول إلى 48 ساعة وإلغاء الجلسات والخانات، ورفض الدخول دون TOTP بعد تفعيله، وفصل أخطاء كود الاستخدام عن عداد TOTP، وإنشاء 350 مفتاح استرداد فريدًا، وتخزين البصمات فقط، وتدوير مفتاح خانة واستخدامه مرة واحدة، وظهور أحداث الاسترداد في غرفة المطور.
- `python -m py_compile app/main.py scripts/*.py eo_vault_runtime.py vault_bootstrap.py`: ناجح.
- `node --check docs/assets/app.js` و`v5.js` و`workspace.js` و`sw.js`: ناجح.
- فحوص YAML وJSON وXML وBash وسلامة ZIP: ناجحة. تم التحقق من EO VAULT ثم فك نسخة اختبارية والتحقق من SHA-256 للملفات المحمية.
- سكربت الرفع الخارجي `scripts/termux-upload-sealed.sh` موجود ضمن التوزيع ومغطى ببصمة `loader_files` الموقعة؛ أضيف اختبار يثبت رفض تعديله.
- قوائم الرفع في سكربتات Termux تتضمن Caddyfile وملفات ملاحظات الإصدار ودليل التحديث، وتستبعد المصدر المفكوك.

## إعداد غرفة الاسترداد عند النشر

1. أعد إعداد `TOTP_ENCRYPTION_KEY` ثابتًا وسريًا داخل `.env`.
2. نفّذ `python scripts/generate-emergency-vault-code.py` واحفظ الرمز الذي يظهر مرة واحدة داخل مدير كلمات مرور آمن. استخدم `--rotate` فقط عند استبداله عمدًا.
3. (اختياري) نفّذ `python scripts/generate-developer-access-code.py` لإنشاء كود حصة 24 ساعة؛ استخدم `--rotate` فقط عند تغييره عمدًا.
4. أعد تشغيل خدمة الويب بعد إعداد المتغيرات.
5. من غرفة المطور أدخل مفتاح الغرفة وTOTP، ثم اختر «إنشاء مفاتيح الخانات التي لا تملك مفتاحًا» لتوليد مفاتيح 350 خانة وتنزيل CSV مرة واحدة. احفظ CSV خارج الموقع والخادم.
6. لا تستخدم الرمز الذي سبق كتابته في المحادثة ككلمة مرور لغرفة الاسترداد؛ اعتبره مكشوفًا وأنشئ رمزًا جديدًا.

## ما لا يمكن إثباته في بيئة التطوير الحالية

- بناء APK فعلي وتوقيعه وتثبيته على هاتف Android؛ Android SDK وGradle غير متاحين في بيئة البناء الحالية. فحص Kotlin parser لم يجد أخطاء تركيب، لكنه ليس بديلًا عن Gradle compile. Workflow يبني Debug، ويبني Release موقعًا فقط عند ضبط أسرار keystore، ولم يُنفذ هنا.
- تشغيل PostgreSQL وDocker على VPS فعلي مع HTTPS وTURN حقيقي.
- اختبار ربط ومشاهدة شاشة فعليين بين هاتف وكمبيوتر على شبكتين مختلفتين.
- اختبار PWA على Windows فعليًا.
- اختبار تحمل 350 اتصال إدارة أو 300 بث فيديو متزامن؛ اختبارات غرف الإشارة لا تثبت قدرة بث الفيديو.
- اختبار اختراق مستقل وتدقيق أمني خارجي.

**الحكم:** وظائف المصادقة وغرفة الاسترداد وإعادة ضبط الخانات لها تنفيذ واختبارات مصدرية. لا يُوصف الإصدار بأنه إصدار إنتاج نهائي حتى ينجح بناء Android والنشر واختبارات الأجهزة الفعلية والتحمل.


## EO VAULT source-protection layer

- EO VAULT payload format: AES-256-GCM with a separate 256-bit random master key.
- EO INTEGRITY SEAL: canonical manifest with SHA-256 hashes for every packaged file, authenticated by Ed25519 signature.
- The public trust anchor is pinned by SHA-256 inside the small runtime verifier.
- Production Docker image copies encrypted payload + minimal bootstrap/verifier only; app source is decrypted into a restricted tmpfs at startup.
- Developer tooling supports key generation, sealing, signature/payload verification, and source decryption.
- Security tests cover round trip, wrong master key, ciphertext tampering, manifest tampering, loader tampering, per-file SHA-256 tampering, trust-anchor replacement, path traversal, missing master-key fail-closed behavior, and key-size validation.
- Browser HTML/JavaScript/CSS is readable once delivered to the browser; encryption protects files at rest and in the sealed package, not against inspection by the browser recipient.

- Termux upload scripts were changed to stage an explicit allowlist of sealed artifacts only, not the decrypted source tree.
- GitHub Actions workflows verify the signed encrypted payload, decrypt to ephemeral runner storage using the `EO_MASTER_KEY` repository secret, then test/build from that temporary source tree.


## ما تم اختباره في طبقة EO VAULT

- حُزمت 61 مادة مصدرية من التطبيق والواجهة وAndroid والبرامج النصية والاختبارات والإعدادات داخل `vault/eo_vault.bin`.
- نجح التحقق من بيان SHA-256 الموقع ثم فك نسخة مطابقة والتحقق من بصمة كل ملف.
- جُرّب مفتاح خاطئ، وتغيير الحمولة، وتغيير البيان، وتغيير مشغل الإقلاع، واستبدال المفتاح العام، وتغيير ملف بعد فك الحمولة؛ جميعها رُفضت.
- أداة التحقق والفتح ومفتاح التشفير ومفتاح التوقيع الخاص مفصولة؛ لا يوجد أي مفتاح خاص داخل حزمة التوزيع.
- لم يتم بناء Docker image لأن Docker/Podman غير متاحين في بيئة العمل الحالية.


## Termux credential helper

- Added root `termux-eo.sh` with `save`, `update-token`, `status`, `forget`, `push`, `install-keys`, `open-source`, `seal-source`, and `actions-key` commands.
- GitHub username/token/repository are stored outside the project under Termux private HOME with mode 0600; no token is saved in Git configuration or remote URLs.
- Upload uses a restricted file allowlist and verifies EO INTEGRITY SEAL before staging.
- Added tests for save path, private permissions, token not echoed, status redaction, forget, and unified legacy uploader entrypoint.
