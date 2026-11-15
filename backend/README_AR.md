# الخدمات السحابية المطلوبة قبل التشغيل الإنتاجي

واجهة `docs/` ثابتة وتعمل على GitHub Pages. الوظائف التالية غير مفعلة في الإصدار الأول لأنها تحتاج API وقاعدة بيانات وخدمة Android:

1. تسجيل الحسابات والجلسات.
2. حجوزات ذرية للخانات الـ300 ومنع الحجز المزدوج.
3. إصدار روابط ربط عشوائية أحادية الاستخدام بصلاحية 15 دقيقة.
4. إدارة المستخدمين والحظر وتسجيل الإجراءات الإدارية.
5. حد الاستخدام اليومي المشترك بين الأجهزة.
6. مهلة الخمول 14 يومًا مع إنهاء الجلسات فقط، دون حذف بيانات الهاتف.
7. خدمة signaling وWebRTC لعرض الشاشة بموافقة ظاهرة من مالك جهاز Android.
8. إدارة مفاتيح منفصلة للخانات عبر KMS.

## مبادئ API المقترحة

- `GET /health`
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/slots`
- `POST /v1/slots/{slotId}/reserve`
- `POST /v1/slots/{slotId}/pairing-links`
- `POST /v1/pairing-links/redeem`
- `POST /v1/sessions`
- `DELETE /v1/sessions/{sessionId}`
- `GET /v1/me/usage`
- `GET /v1/admin/users?query=`
- `POST /v1/admin/users/{userId}/revoke-sessions`

تُحمى جميع المسارات بصلاحيات server-side، مع التحقق من ملكية الخانة وموافقة صاحب الجهاز. لا تُنفذ أفعال الإدارة من JavaScript وحده.
