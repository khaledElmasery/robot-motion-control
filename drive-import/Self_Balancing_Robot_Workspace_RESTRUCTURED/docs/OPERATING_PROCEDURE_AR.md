# إجراء التشغيل القياسي v3

## المرحلة 1 — الكهرباء

افصل البطارية. اختر نمطًا واحدًا فقط. طابق `hardware/PINOUT_AND_POWER_AR.md`. تحقق من GND، مقاومات LEDs، مقسم Echo، ومحول مستويات UART. لا توصل 12V إلى Arduino أو ESP32 أو MPU6050.

## المرحلة 2 — Arduino Standalone

وصل MPU6050 فقط، ارفع `firmware/common/UnifiedBalance.ino` بإعداد Arduino أو استخدم نسخة Arduino المستقلة، وافتح Serial على 115200. نفذ المعايرة وهو مستوٍ، ثم اختبر قراءة الزاوية. ارفع العجلات، اختبر كل محرك بقدرة منخفضة، واضبط PID تدريجيًا: Ki=0 وKd=0، ثم Kp، ثم Kd، ثم Ki.

## المرحلة 3 — الحماية والواجهات

أضف HC-SR04 واختبر أن عائقًا أقل من 100cm يمنع الأمر الأمامي عبر setpoint آمن. أضف LEDs. لا تضف IR قبل التقاط الأكواد الحقيقية. لا تضف FD650 قبل datasheet أو Logic Analyzer.

## المرحلة 4 — Bridge

افصل البطارية، انقل UART فقط عبر level shifter، واضبط MODE_PIN على LOW. Arduino يشغل PID، وESP32 يمرر الأوامر ويقرأ أسطر `TEL`. تحقق من أن Telemetry تصل إلى `/api/telemetry` وأن الأوامر لا تشغل PID على ESP32 في Bridge.

## المرحلة 5 — Cloud

شغّل `cloud-backend/server.js` مع `CONTROL_TOKEN` غير افتراضي. ضع عنوان الخادم وSSID وWi‑Fi والرمز في Unified Firmware، ثم اختبر Dashboard وSSE. لا تنشر HTTP على الإنترنت؛ استخدم HTTPS وreverse proxy ومصادقة وتحديد معدل الطلبات.

## المرحلة 6 — AP الطوارئ

افصل الخادم أو Wi‑Fi. يجب أن يحاول ESP32 STA ثم يعود إلى `BalanceBot-Setup` عند الفشل. اتصل بالهاتف وافتح `/cmd` و`/telemetry` أو ارفع ملفات `firmware/esp32/data` إلى SPIFFS/LittleFS حسب بيئة البناء.

## المرحلة 7 — الإيقاف

اختبر Stop، فقد Dashboard، فقد Wi‑Fi، أمرًا غير معروف، عائقًا، وميلًا يتجاوز 35°. لا تضع البطارية أو الحمولة إلا بعد نجاح الاختبارات والعجلات مرفوعة أولًا.
