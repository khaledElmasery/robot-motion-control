# سجل التغييرات

## v3 — Unified + Cloud

- إضافة README شامل إلى `docs/README_AR.md`.
- إضافة `firmware/common/UnifiedBalance.ino` بفروع `#ifdef ARDUINO` و`#ifdef ESP32`.
- فصل Bridge: Arduino يشغل الاتزان، وESP32 يمرر الأوامر ويقرأ Telemetry.
- إضافة Cloud Backend HTTP/SSE مع token.
- تحديث Dashboard لاستخدام API وSSE.
- إضافة ملفات واجهة طوارئ لـSPIFFS/LittleFS.
- توحيد UART2 وHC-SR04 وLEDs وIR في pinout.
- تحديث مخططات TeX وWokwi README.

## حدود معلنة

IRremote وFD650 يحتاجان أكواد ريموت وdatasheet/قياسًا حقيقيًا، ولا يجوز اختراعهما. Wokwi لا يثبت سلامة الدارة الميكانيكية، وcompile/المعايرة النهائية يحتاجان لوحات فعلية.
