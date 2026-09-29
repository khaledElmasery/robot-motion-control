# BalanceBot Dashboard

واجهة D-pad وTelemetry. تعمل عبر Cloud Backend عند `/api/command` و`/api/stream`، وتقبل رمز `CONTROL_TOKEN` من المستخدم. يمكن استعمالها محليًا مع نفس الواجهة إذا استُخدمت نقاط ESP32 المحلية بدل Backend. لا تنشرها على الإنترنت دون HTTPS ومصادقة وتحديد معدل الطلبات.
