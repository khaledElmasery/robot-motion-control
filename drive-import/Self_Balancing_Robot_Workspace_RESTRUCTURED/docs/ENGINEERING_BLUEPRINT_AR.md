# المخطط الهندسي الشامل v3

## المسار الحرج

`MPU6050 → complementary filter → PID → PWM/direction → L298N → motors`. الاتصالات الخارجية تدخل أوامر محدودة فقط. في Bridge لا يشغل ESP32 PID؛ يمرر الأوامر ويعيد Telemetry. في Standalone يشغل ESP32 PID بنفسه.

## الطبقات

1. **Firmware:** `firmware/common/UnifiedBalance.ino` يحوي `#ifdef ARDUINO` و`#ifdef ESP32`.
2. **Local fallback:** WebServer وAP محليان على ESP32 عند تعذر السحابة.
3. **Cloud:** `cloud-backend/server.js` يستقبل الأوامر وTelemetry ويبث SSE للوحة.
4. **Dashboard:** `web-dashboard/` واجهة D-pad وTelemetry.
5. **Hardware extras:** HC-SR04 منفذ؛ IR وFD650 يحتاجان قياسًا وبيانات حقيقية قبل إغلاق التنفيذ.

## مبدأ الهجين

يتصل ESP32 بالسحابة في وضع STA ويحاول نشر Telemetry وجلب الأمر. إذا فشل الاتصال، يعود إلى AP محلي. لا يعني AP المحلي أن الصفحة مناسبة لآلاف المستخدمين؛ هو قناة طوارئ قريبة.

## receiver القديم

IR يمر إلى مدخل مستقل بعد التحقق من الجهد والتقاط الأكواد عبر IRremote. FD650 لا يُفترض بروتوكوله؛ افحص DAT/CLK وADD/5V وGND بــdatasheet أو Logic Analyzer قبل إنشاء Driver.
