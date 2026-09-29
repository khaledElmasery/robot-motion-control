# BalanceBot Cloud Backend

خادم Node.js بسيط بلا حزم خارجية. يستضيف Dashboard ويوفر قناة أوامر وTelemetry عبر HTTP وSSE.

## التشغيل

```bash
CONTROL_TOKEN='ضع-رمزًا-طويلًا' PORT=8080 node server.js
```

افتح `http://HOST:8080/`. عرّف في Unified Firmware عنوان الخادم نفسه، وSSID وكلمة المرور والرمز نفسه. لا تستخدم `localhost` داخل ESP32 إذا كان الخادم على جهاز آخر.

## المسارات

- `POST /api/command` مع `{"command":"F"}`.
- `GET /api/device/command` لقراءة الأمر الحالي من ESP32.
- `POST /api/telemetry` لإرسال JSON من ESP32.
- `GET /api/state` لقراءة الحالة.
- `GET /api/stream` لبث SSE للواجهة.

كل مسارات API تتطلب `Authorization: Bearer CONTROL_TOKEN`. هذا Backend مناسب للتجربة والتطوير؛ للنشر العام استخدم HTTPS وreverse proxy ومصادقة متعددة المستخدمين وتحديد معدل الطلبات وسجل تدقيق. لا تجعل الرابط عامًا دون حماية.
