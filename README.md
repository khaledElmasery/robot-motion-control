# مشروع حركة الروبوت والتحكم اليدوي

مشروع تعليمي لسيارة روبوتية صغيرة تعمل بمحركين DC، ويتيح بناء **ملف C++ واحد** لثلاثة أوضاع: Arduino Uno R3، أو ESP32 كجسر Bluetooth إلى Uno، أو ESP32 مستقل. يقرأ برنامج Python يد التحكم ويرسل أوامر قصيرة؛ ويقود المتحكم المحركات عبر L298N ويقرأ الحساسات والبازر.

> **مهم:** توثّق هذه الصفحة النسخة الحالية من المشروع، لكن لم تُبرمج لوحة فعلية أو تُختبر التوصيلات على الروبوت. لم يُحدد طراز ESP32 الكامل في مواصفات القطع؛ لذلك إعداد ESP32 هنا مخصص للوحة 30-pin الشائعة ذات وحدة **ESP32-WROOM-32** (`esp32dev`) وليس S3/C3/WROVER دون تعديل.

> **تنبيه طاقة وسلامة:** محركات TT المذكورة مصنفة 3–6V، بينما حزمة 3S تصل إلى 12.6V. لا توصلها مباشرة للمحركات أو مدخل المحرك في L298N؛ يلزم Buck مضبوط ومناسب للتيار، ومصدر 5V منظم للمنطق حسب لوحة القيادة. حماية HC‑SR04 أمامية محدودة ولا تمنع كل الاصطدامات. ابدأ دائمًا بالعجلات مرفوعة، ومفتاح فصل الطاقة في يد المشغّل. راجع أيضًا ملاحظة الدايودات في [دليل التوصيلات](docs/WIRING_AND_HARDWARE.md) قبل تشغيل المحركات.

## ابدأ من هنا

1. اقرأ [فهرس الوثائق](docs/README_AR.md).
2. طابق اللوحة الفعلية أولًا، ثم اتبع [جداول التوصيلات المسماة](docs/WIRING_AND_HARDWARE.md) ودليل [التبديل بين Uno المباشر والهجين](docs/MODE_SWITCH_DIRECT_HYBRID_AR.md).
3. راجع [السلامة والاختبار](docs/SAFETY_AND_TESTING.md) قبل توصيل تغذية المحركات.
4. تحقق من أرقام أزرار يد PlayStation باستخدام [دليل جسر Python](scripts/README_AR.md) ووضع `--probe-controllers`.
5. راجع [خريطة التحكم](docs/CONTROLLER_MAPPING.md) و[دليل البازر](docs/BUZZER_MUSIC_AR.md).
6. لمعرفة الملفات التي لم تُنقل حرفيًا من الأرشيف القديم، اقرأ [مقارنة Buzzer_Music](docs/ARCHIVE_COMPARISON_AR.md).
7. في الوضعين المباشر والهجين تظل المكونات على Uno؛ يشرح [دليل مفتاح الوضع](docs/MODE_SWITCH_DIRECT_HYBRID_AR.md) عزل UART والتغذية.
8. عند ظهور مشكلة، ابدأ بـ[دليل استكشاف الأخطاء وإصلاحها](docs/TROUBLESHOOTING_AR.md).
9. راجع [دليل محاكاة Wokwi](simulation/wokwi/README_AR.md) لنطاق الاختبارات الافتراضية وحدودها؛ المحاكاة لا تثبت سلامة العتاد الفعلي.

> **حالة التحقق الافتراضي (2026-10-01):** اجتازت ملفات المشروع فحص Wokwi المحلي والبناء واختبارات Python، لكن تشغيل السيناريوهات الفعلية لم يكتمل: لم يتوفر `WOKWI_CLI_TOKEN`، ومحاولة المتصفح بقيت في طابور `Build server load` ثم أُلغيت. لم تصل صورة مخطط كهربائي؛ الصورة المتاحة لقطة شاشة للكود وتعرض خريطة أرجل مختلفة عن النسخة الحالية. التفاصيل في [سجل المحاكاة](simulation/wokwi/README_AR.md) و[دليل استكشاف الأخطاء](docs/TROUBLESHOOTING_AR.md).

> **الأسماء المطبوعة مقابل قيم C++:** جداول الأسلاك تعرض علامة PWM على Uno مثل `~5`، وتستخدم `GPIO25` كصيغة واضحة لرجل ESP32 (قد تطبع بعض اللوحات `IO25`). هذه العلامات والبادئات للتعريف وليست جزءًا من قيمة الطرف التي تمررها دوال Arduino؛ لذلك `ENA_PIN 5` يطابق طرف Uno `~5`، والرقم `25` في الكود يطابق GPIO25. تسميتا UART على Uno موضحتان `TX→1` و`RX←0` في [دليل التوصيلات](docs/WIRING_AND_HARDWARE.md).

## ما الذي ينفذه البرنامج؟

- تحكم يدوي لمحركين عبر L298N، مع تعديل المستوى بين 0 و10 باستخدام أزرار السرعة.
- عصا اليسار للحركة الأساسية؛ `R2` للأمام و`L2` للخلف؛ `Y + R2/L2` للدوران في المكان؛ R1/L1 لتشغيل عجلة واحدة؛ والأسهم لدفعات/دورانات زمنية.
- جسر Python واحد يعمل عبر USB Serial أو منفذ COM افتراضي من Bluetooth Classic SPP. Wi‑Fi/TCP غير مضاف في هذه النسخة.
- إرسال نبضات حياة `Z` من الجسر كل 100ms؛ يوقف البرنامج المحركات بعد نحو 350ms عند انقطاعها. أوامر Serial اليدوية دون `Z` لا تُسلح هذا الـwatchdog.
- HC‑SR04 أمامي يحجب بعض أوامر التقدم إذا فشل القياس أو كانت المسافة أقل من 15cm.
- MPU6050 يعطي تقدير ميل تقريبيًا لأوامر `^` و`V`؛ لا توجد معايرة جيروسكوب أو اتزان PID.
- مقاومة متغيرة للتحكم في duty-cycle البازر، وأربعة أنماط نغمية أحادية الصوت مع تنبيه منفصل. ليست ملفات صوتية أو أغانٍ متعددة الأصوات.
- IR مهيأ كمدخل فقط، ولا يوجد فك إشارة ريموت حتى الآن.

## البناء

ثبّت إضافة PlatformIO IDE أو PlatformIO Core، ثم من جذر المشروع نفّذ بيئة واحدة فقط:

```bash
pio run -e uno
pio run -e esp32_bridge
pio run -e esp32_standalone
```

- `uno`: Arduino Uno R3؛ برنامج المتحكم على Uno.
- `esp32_bridge`: ESP32-WROOM-32 يعمل كوسيط Bluetooth Classic SPP إلى Uno عبر UART2.
- `esp32_standalone`: ESP32-WROOM-32 يشغّل المحركات والحساسات مباشرة بعد نقل الأسلاك إلى خريطته.

كل الأوضاع تبني من `src/main.cpp`. لا يعني نجاح البناء أن الأسلاك أو جهد المحركات صحيح. لا تستخدم `pio run -t upload` إلا بعد مطابقة اللوحة والتوصيلات وفصل طاقة المحركات.

## Python والتحكم

من جذر المشروع:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/requirements.txt
python scripts/bridge.py --list-ports
python scripts/bridge.py --list-controllers
python scripts/bridge.py --probe-controllers
python scripts/bridge.py --self-test
```

بعد إقران Bluetooth Classic على الكمبيوتر، اختر منفذ SPP الذي يظهر ضمن المنافذ، مثل `COM8` على Windows أو `/dev/rfcomm0` على Linux:

```bash
python scripts/bridge.py --port COM8
```

الأرقام الافتراضية في الملف قيم بدء مستنتجة من إعداد يدك وليست مضمونة. استخدم `--probe-controllers` قبل توصيل طاقة المحركات؛ يستطيع `--spin-modifier-button N` تعديل زر Y/المثلث وغيره. التفاصيل في [دليل الجسر](scripts/README_AR.md).

## مستويات PWM لا تعني RPM

المستوى 0 يطلب PWM=0، والمستويات 1–10 ترسل قيم PWM من 50 إلى 255 إلى ENA/ENB. هذا تحكم مفتوح الحلقة بلا مشفرات عجلات، لذلك لا يضمن سرعة فعلية أو استجابة خطية. إذا تغيرت رسالة `SPEED_LEVEL` ولم تتغير سرعة المحركات، افحص جسري ENA/ENB ومصدر الطاقة وهبوط الجهد في L298N وتوصيل مخارج PWM.

## خريطة الملفات

```text
.
├── platformio.ini                 # بيئات Uno وESP32 bridge وESP32 standalone
├── src/
│   ├── main.cpp                   # مصدر C++ موحد بفروع حسب اللوحة/الدور
│   └── README_AR.md              # شرح بناء firmware وأجزائه
├── scripts/
│   ├── bridge.py                  # ربط يد التحكم عبر USB أو Bluetooth Serial
│   ├── requirements.txt           # إصدارات pygame وpyserial
│   └── README_AR.md              # التثبيت والفحص والتشغيل
├── tests/test_bridge.py           # اختبارات خرائط الجسر والبروتوكول
├── docs/
│   ├── README_AR.md              # فهرس الوثائق
│   ├── WIRING_AND_HARDWARE.md    # جداول أطراف Uno وESP32 والطاقة
│   ├── MODE_SWITCH_DIRECT_HYBRID_AR.md # مفتاح الانتقال الآمن بين Uno المباشر والهجين
│   ├── CONTROLLER_MAPPING.md     # الأزرار والمحاور وبروتوكول Serial
│   ├── BUZZER_MUSIC_AR.md        # الأنماط والتحكم التقريبي في الصوت
│   ├── SAFETY_AND_TESTING.md     # القيود وخطوات الاختبار
│   ├── TROUBLESHOOTING_AR.md    # تشخيص أخطاء التوصيل وVS Code والمخطط المختلف
│   ├── ARCHIVE_COMPARISON_AR.md  # ما استُبعد من الأرشيف القديم ولماذا
│   └── HISTORICAL_CONTENT_AND_LICENSES_AR.md # حدود الملفات القديمة والرخص
├── simulation/wokwi/              # مخطط محاكاة Uno ومسودات السيناريوهات
├── .github/                      # قوالب بلاغات المشكلات وطلبات التغيير
├── CONTRIBUTING.md               # إرشادات المساهمة
├── CHANGELOG.md                  # سجل تغييرات النسخة
├── UNLICENSE                     # رخصة الملفات التي يملك المشروع حق ترخيصها
├── .gitignore                    # استثناء البناء والبيئات المحلية
└── .vscode/extensions.json       # توصية إضافة PlatformIO IDE
```

## أهم الحدود المعروفة

- الزوايا الزمنية `>` و`<` مضبوطة مبدئيًا على 200ms فقط؛ لا تضمن 45° قبل معايرة الهيكل والبطارية والسطح.
- حماية المسافة لا تغطي الرجوع أو الجوانب أو كل حركات الدوران، ولا تضمن منع الاصطدام.
- قراءة MPU6050 تقريبية؛ وIR لا ينفذ أوامر بعد.
- ESP32 المقصود هو طراز أصلي يدعم Bluetooth Classic SPP؛ وضع Wi‑Fi غير مطبق.
- يجب التأكد من أن البازر لا يتجاوز تيار GPIO. شدة الصوت الفعلية لم تُعاير بالديسيبل.
- اجتياز بناء PlatformIO واختبارات Python لا يثبت السلامة الميكانيكية أو الكهربائية؛ يلزم اختبار العتاد بحذر.

## مراجع رسمية

- [مواصفات Arduino Uno R3](https://docs.arduino.cc/hardware/uno-rev3)
- [لوحة PlatformIO `esp32dev`](https://docs.platformio.org/en/latest/boards/espressif32/esp32dev.html)
- [Bluetooth Classic وSPP في Arduino-ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/bluetooth.html)
- [LEDC PWM في Arduino-ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html)
- [ورقة بيانات L298](https://www.st.com/resource/en/datasheet/l298.pdf)
