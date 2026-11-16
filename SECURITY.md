# SECURITY — ALMANTHOMH EO CN EAGLE NEXUS V5.0.0

## إعداد الإنتاج
- استخدم HTTPS صالحًا و`COOKIE_SECURE=true`.
- خزّن `.env` خارج GitHub بصلاحيات مقيدة. لا ترفع مفاتيح قاعدة البيانات أو bootstrap أو TURN أو كود المطور.
- احذف `ADMIN_BOOTSTRAP_KEY` بعد إنشاء أول مدير.
- استخدم PostgreSQL ونسخًا احتياطية خارج الخادم.
- اجعل الواجهة وAPI على نفس الأصل عبر Reverse Proxy.

## الهوية والأكواد
- كلمات المرور تستخدم PBKDF2-HMAC-SHA256 مع salt فريد.
- تُخزن رموز الجلسات والربط واعتمادات الأجهزة بصيغة hash، وليس كنص صريح.
- الحد الأساسي ساعتان يوميًا؛ كود المستخدم `ALMANTHOMH1234567890` يرفع الحد إلى 6 ساعات يوميًا بعد TOTP.
- كود المطور يتم توليده عشوائيًا على الخادم عبر `scripts/generate-developer-access-code.py` ويُخزن Hash في `.env`. لا يُرسل الكود إلى الواجهة ولا يُسجل في Git.
- كود المطور يغير `access_tier` فقط ولا يمنح `role=admin`، ولا يسمح بفتح لوحة الإدارة.
- تفعيل الأكواد يفرض حدًا لمحاولات الخطأ. غيّر كود المستخدم إذا أصبح غير خاص بالمنظومة؛ الكود المضمّن في وثائق المصدر معروف لمن يملك المصدر.

## جلسات Android المستقلة
- جلسات تطبيق Android تستخدم Bearer tokens عشوائية؛ الخادم يخزن SHA-256 digest ولا يخزن الرمز الخام.
- التطبيق يحفظ الرمز داخل Android Keystore باستخدام AES-GCM؛ كلمة مرور الحساب لا تُحفظ محليًا.
- عند تفعيل TOTP، يُطلب الرمز عند تسجيل دخول Android جديد. تُلغى جلسات التطبيق عند قفل المصادقة لمدة 48 ساعة، أو قفل الطوارئ، أو إلغاء صلاحيات الحساب.
- تسجيل خروج جلسة التطبيق لا يلغي اعتماد الجهاز المرتبط؛ يجب إلغاء ربط الجهاز صراحةً.

## استخدام وخصوصية
- عداد الاستخدام يعتمد نبضات مشتركة بين صفحة الويب/الكمبيوتر الظاهرة وتطبيق Android في المقدمة وخدمة مشاركة الشاشة أثناء نشاطها. لا يراقب بقية أنشطة الجهاز خارج التطبيق.
- تُستخدم خانة يومية واحدة للحساب لمنع مضاعفة الوقت عند فتح أكثر من قناة. فترات الانقطاع الطويلة لا تُحتسب كاستخدام مستمر.
- الحد الأساسي ساعتان؛ المستخدم بعد التفعيل 6 ساعات في اليوم؛ المطور/المدير: حتى 24 ساعة في اليوم، وفق توقيت القاهرة.
- مجموعة الكمبيوتر 50 خانة منفصلة عن 300 خانة الهاتف. الحجز مرتبط بالحساب ولا يسمح بخانة PC متعددة للمستخدم نفسه.
- لا يحصل المتصفح على تحكم بالكمبيوتر أو الهاتف عبر حجز خانة PC.

## مشاركة الشاشة
- التقاط الشاشة لا يبدأ لمجرد الربط.
- صاحب Android يوافق من نافذة MediaProjection الرسمية، ويوافق منفصلًا على كل جلسة مشاهدة.
- إشعار Foreground دائم مع زر إيقاف؛ لا توجد أوامر لمس أو لوحة مفاتيح أو تحكم خفي.
- لا تستخدم Accessibility أو صلاحيات مخفية لتجاوز الموافقة.

## حدود التحقق
- فحوصات المصدر لا تغني عن بناء APK وتجربته على أجهزة حقيقية.
- GitHub Pages لا يستضيف FastAPI أو PostgreSQL.
- عدد الخانات لا يثبت قدرة بث متزامن؛ نفّذ load test على بنية الإنتاج.
- لم يجر تدقيق اختراق مستقل في هذه الحزمة.

## الإبلاغ
لا ترسل كلمات المرور أو رموز الربط أو Bearer tokens أو مفاتيح الخادم داخل البلاغ. أرسل وصفًا عامًا ورقم الإصدار والوقت.

## Two-factor authentication and progressive lockout

- Access-code redemption requires an enrolled RFC 6238 TOTP authenticator code (6 digits).
- Enroll from the signed-in account panel using `/api/auth/2fa/setup`, add the returned secret to a trusted authenticator app, then confirm via `/api/auth/2fa/confirm`.
- TOTP secrets are encrypted at rest with `TOTP_ENCRYPTION_KEY`. Production deployments must set a private, persistent Fernet key and protect its backup. Never commit the production key.
- Three consecutive incorrect TOTP entries trigger a 10-minute lock. After that, each two further incorrect entries double the lock duration: 20, 40, 80 minutes, capped at 48 hours. A successful code resets the escalation counter.
- The base daily quota is 2 hours. The user access code raises it to 6 hours/day. The developer access code raises it to 24 hours/day but does not grant administrator permissions.


## المصادقة الثنائية والتصعيد

- بعد تفعيل TOTP يصبح الرمز مطلوبًا عند تسجيل الدخول الجديد، وكذلك عند تفعيل كود الاستحقاق وفتح غرفة الاسترداد. لا يتم فحص TOTP عند إدخال كود استحقاق غير صحيح؛ الكود الخاطئ لا يزيد عداد أخطاء TOTP. تبقى أكواد الاستحقاق محمية بمحدد إساءة استخدام مستقل.
- أول 3 أخطاء TOTP تقفل التحقق 10 دقائق. بعد ذلك كل خطأين إضافيين يضاعفان المدة: 20، 40، 80 دقيقة… حتى 48 ساعة.
- عند الوصول إلى قفل 48 ساعة، تُلغى جلسات الحساب، وتُحرر خانات الهاتف والكمبيوتر، وتُلغى اعتمادات الأجهزة وروابط الربط، وتُنهى جلسات المشاهدة. هذا «soft reset» لخانات المنظومة فقط؛ لا يعيد تشغيل الهاتف ولا يمسح بياناته.
- كل محاولة TOTP والأقفال وعمليات إعادة الضبط تسجل في `security_events` وتظهر في غرفة المطور.

## غرفة الاسترداد

- لا تخزن المنظومة كلمات مرور المستخدمين بصيغة قابلة للقراءة، ولا توجد كلمة مرور رئيسية تفتح كل الحسابات.
- غرفة الاسترداد تتطلب حساب ADMIN ومصادقة TOTP ومفتاحًا منفصلًا مخزنًا كبصمة SHA-256 في `EMERGENCY_VAULT_CODE_HASH`.
- أنشئ المفتاح بواسطة `python scripts/generate-emergency-vault-code.py`. لا تستخدم رمزًا سبق مشاركته أو نشره.
- لكل خانة هاتف أو كمبيوتر مفتاح استرداد مختلف، أحادي الاستخدام. المخزن يحتوي بصمة المفتاح فقط؛ يعرضه الخادم مرة واحدة عند التدوير.
- استهلاك مفتاح الخانة يحررها ويلغي الجلسات واعتمادات الأجهزة المرتبطة بها. لا يسمح بتسجيل الدخول كالمستخدم ولا بتجاوز موافقة صاحب الجهاز على المشاهدة.
- فشل مفتاح غرفة الاسترداد له محدد مستقل: 5 محاولات في 15 دقيقة، ولا يزيد عداد TOTP.

### كود المطور (حصة الاستخدام فقط)

أنشئ كودًا عشوائيًا يظهر مرة واحدة باستخدام `python scripts/generate-developer-access-code.py`. لتدويره لاحقًا استخدم `--rotate`. يُخزّن الخادم بصمة SHA-256 فقط، ويمنح 24 ساعة استخدام يوميًا ولا يمنح دور ADMIN. أعد تشغيل خدمة الويب بعد التوليد.


## Source protection

The sealed release stores application, frontend, Android, scripts, tests, and deployment source inside an AES-256-GCM encrypted EO VAULT payload. A signed manifest provides per-file SHA-256 digests. Ed25519 authenticates that manifest; SHA-256 alone is not treated as an authenticity mechanism. The master decryption key and signing private key must remain outside source control and release artifacts. Runtime plaintext is extracted only to a restricted temporary filesystem. Browser-delivered frontend code is necessarily readable by the browser; no client-side scheme can keep delivered HTML/JS/CSS secret from the recipient.


## GitHub token persistence in Termux

The Termux helper stores the GitHub username, PAT, and repository URL in `$HOME/.config/almanthomh-eo-cn/github-credentials` with directory mode 0700 and file mode 0600. It is intentionally outside the project and is never staged by the uploader. The PAT is plaintext in Termux's app-private storage for convenience; this is not encryption against root or a compromised device. Use a fine-grained PAT scoped only to repository contents write access, revoke it if the device is lost, and never share the credential file. Git is invoked with an empty credential helper and a temporary/private askpass helper; credentials are not persisted in `.git/config`, the global Git config, or the remote URL.
