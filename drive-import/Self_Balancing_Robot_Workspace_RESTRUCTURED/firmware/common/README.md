# بروتوكول BalanceBot v3

الأوامر المسموحة حرف واحد: `F` أمام، `B` خلف، `L` يسار، `R` يمين، `S` توقف. تنتهي صلاحية الأمر بعد 1000ms. في Bridge يرسل ESP32 الأمر إلى Arduino عبر UART2 بعد تحويل مستوى 3.3V/5V.

Telemetry من Arduino: `TEL angle=-0.12 output=3.40 distance=142.0 command=S mode=arduino`. يقرأ ESP32 Bridge هذه السطور ويعيد نشرها إلى `POST /api/telemetry` في Cloud Backend. في Standalone يرسل ESP32 JSON مباشرة.

JSON: `angle`, `output`, `distance`, `command`, `mode`, `uptime`. المسارات السحابية هي `/api/command`, `/api/device/command`, `/api/telemetry`, `/api/state`, و`/api/stream`. استخدم `Authorization: Bearer CONTROL_TOKEN`، ولا تنشر بدون HTTPS ومصادقة وتحديد معدل الطلبات.
