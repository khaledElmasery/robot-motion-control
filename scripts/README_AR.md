# جسر يد التحكم — Python

`bridge.py` يقرأ يد PlayStation/X360CE باستخدام `pygame` ويرسل أحرف Serial منفردة إلى Uno أو ESP32. لا يقود المحركات مباشرة؛ firmware هو الذي يفسر الأوامر. يعمل الجسر على منفذ USB Serial أو Bluetooth Classic SPP الذي يظهر كمنفذ COM/Serial افتراضي. لا يوجد دعم Wi‑Fi/TCP في هذا الإصدار.

| الملف | وظيفته |
|---|---|
| `bridge.py` | قراءة الأزرار والمحاور، إرسال الأوامر وheartbeat، وعرض ردود السرعة. |
| `requirements.txt` | إصدارات pygame وpyserial المثبتة للمشروع. |

## التثبيت

يتطلب Python 3.10 أو أحدث. من جذر المشروع:

```bash
python -m venv .venv
```

فعّل البيئة المناسبة لنظامك، ثم:

```bash
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r scripts/requirements.txt
```

## اكتشاف اليد والمنفذ — بلا حركة

```bash
python scripts/bridge.py --list-ports
python scripts/bridge.py --list-controllers
python scripts/bridge.py --probe-controllers
python scripts/bridge.py --self-test
```

`--probe-controllers` لا يفتح منفذ Serial ولا يرسل أوامر للروبوت؛ يعرض تغيّر المحاور والأزرار والـhat. اضغط كل زر منفردًا وسجّل فهرسه. قيم PS1/X360CE الافتراضية تخمينية، وخصوصًا زر Y/المثلث. عدّلها بعد الفحص باستخدام `--spin-modifier-button` وخيارات `--help`.

## تشغيل سلكي أو لاسلكي

أغلق Serial Monitor وأي برنامج آخر فاتح للمنفذ نفسه. عبر USB على Windows مثلًا:

```powershell
python scripts/bridge.py --port COM8
```

بعد إقران `Robot_Motion_Bridge` أو `Robot_Motion_Control` عبر Bluetooth Classic، اختر منفذ SPP الافتراضي الذي أنشأه نظام التشغيل؛ قد يكون COM على Windows أو `/dev/rfcomm0` على Linux:

```bash
python scripts/bridge.py --port COM8
```

في وضع ESP32 bridge يظل Uno متصلًا بـUART2 على 9600 baud. قيمة `--baud` الافتراضية 9600 مطابقة لرابط Uno؛ منفذ Bluetooth نفسه افتراضي ويعرضه النظام كـCOM/Serial.

## التحكم الافتراضي

- العصا اليسرى: أمام/خلف/يمين/يسار؛ المركز يطلب `S`.
- R2 وحده يرسل `F` للأمام، وL2 وحده يرسل `B` للخلف؛ مع Y/المثلث يتحول R2 إلى `C` (دوران عكس عقارب الساعة) وL2 إلى `c` (مع عقارب الساعة). ضغط الزنادين معًا يرسل `S`.
- L1 يحرك المحرك الأيسر منفردًا، وR1 يحرك المحرك الأيمن. ضغطهما معًا يطلب `S`.
- Xbox A يرسل `+` لزيادة السرعة مستويين، وXbox X يرسل `-` لخفضها مستويين.
- D-pad يرسل `^/V/< />` مرة واحدة عند الضغط الجديد. `^/V` مشروطان بحساس الميل؛ و`< />` مدتهما 200ms مبدئيًا وليستا زاوية 45° مضمونة.
- العصا اليمنى تختار الأنماط `1` إلى `4`، ونقرها R3 يرسل `H`.
- Space يطلب توقفًا. الأسهم وA/D وQ/E توفر بدائل من لوحة المفاتيح عند تركيز النافذة.

التفاصيل الدقيقة في [خريطة التحكم](../docs/CONTROLLER_MAPPING.md). أما تبديل اللابتوب بين اتصال USB مباشر بـUno ووضع Bluetooth الهجين، فموضح في [دليل مفتاح الوضع](../docs/MODE_SWITCH_DIRECT_HYBRID_AR.md).

## الاتصال والسلامة

يرسل الجسر `Z` كل 100ms. هذا لا يغير الحركة؛ يستخدمه firmware ليوقف المحركات إذا انقطعت نبضات الحياة نحو 350ms. كما يرسل `S` عند فقدان تركيز النافذة أو الخروج الذي يستطيع اكتشافه. لا يغني ذلك عن مفتاح فصل الطاقة، ولا يحمي الحساس كل الاتجاهات.

ابدأ والبطارية مفصولة والعجلات مرفوعة. افحص الفهارس دون طاقة محركات، ثم شغّل الجسر مع وسيلة قطع الطاقة في متناول المشغل. راجع [السلامة](../docs/SAFETY_AND_TESTING.md) و[التوصيلات](../docs/WIRING_AND_HARDWARE.md).
