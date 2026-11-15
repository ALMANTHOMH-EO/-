# الخادم الخلفي V2.0.0

الخادم موجود في `app/main.py` ويعمل باستخدام FastAPI وSQLAlchemy. قاعدة البيانات الافتراضية SQLite للتجربة ذات النسخة الواحدة، مع دعم PostgreSQL عبر `DATABASE_URL` للإنتاج.

المسارات الأساسية:

- `GET /api/health`, `GET /api/config`
- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/me`
- `GET /api/slots`, `POST /api/slots/{id}/reserve`, `DELETE /api/slots/{id}/reserve`
- `POST /api/pairings`, `POST /api/pairings/redeem`
- `POST /api/usage/heartbeat`
- `POST /api/admin/bootstrap`, `GET /api/admin/overview`, `GET /api/admin/users`
- `POST /api/admin/users/{id}/revoke-sessions`, `POST /api/admin/users/{id}/status`, `PATCH /api/admin/slots/{id}`

كل المسارات المعدّلة تتطلب CSRF token. التحقق من المستخدم وصلاحياته يحدث على الخادم. Swagger متاح في `/api-docs`.

رمز الربط يسجل جهازًا مقترنًا فقط. خدمة بث الشاشة والتحكم تحتاج تطبيق Android منفصلًا ولم تُنفذ بعد.
