#include <Arduino.h>
#include <Wire.h>
#include <ctype.h>
#include <stdio.h>

#if defined(ESP32) || defined(ARDUINO_ARCH_ESP32)
  #define ROBOT_PLATFORM_ESP32 1
  #include <BluetoothSerial.h>
  #include <esp_arduino_version.h>
#elif defined(__AVR_ATmega328P__)
  #define ROBOT_PLATFORM_UNO 1
  #include <avr/io.h>
#else
  #error "This firmware supports Arduino Uno R3 or the original ESP32 Dev Module only."
#endif

#if defined(ROBOT_PLATFORM_ESP32)
  #if !defined(ROBOT_ROLE_ESP32_BRIDGE) && !defined(ROBOT_ROLE_ESP32_STANDALONE)
    #error "Select env:esp32_bridge or env:esp32_standalone in PlatformIO."
  #endif
  #if defined(ROBOT_ROLE_ESP32_BRIDGE) && defined(ROBOT_ROLE_ESP32_STANDALONE)
    #error "Select exactly one ESP32 role."
  #endif
  #if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED) || !defined(CONFIG_BT_SPP_ENABLED)
    #error "Bluetooth Classic SPP is required; use an original ESP32-WROOM Dev Board, not an S3/C3."
  #endif
#endif

// ==========================================================
// 📌 [الجزء 1: المنصة والأرجل والمتغيرات العامة]
// ==========================================================

#if defined(ROBOT_PLATFORM_ESP32)

  // خريطة افتراضية للوحة ESP32 Dev Board ذات 30 طرفًا
  // المبنية على الشريحة الأصلية ESP32-WROOM-32.
  #define ENA_PIN 25
  #define ENB_PIN 26
  #define IN1_PIN 27
  #define IN2_PIN 14
  #define IN3_PIN 13
  #define IN4_PIN 23

  #define LED_RED_1 18
  #define LED_RED_2 19
  #define LED_GREEN_1 32
  #define LED_GREEN_2 33

  #define BUZZER_PIN 4
  #define POT_PIN 35
  #define TRIG_PIN 16
  #define ECHO_PIN 17
  #define IR_PIN 34
  #define MPU_SDA_PIN 21
  #define MPU_SCL_PIN 22

  // وضع الجسر يستخدم GPIO16/17 كسيريال UART2 إلى Arduino.
  #define ESP32_LINK_RX_PIN 16
  #define ESP32_LINK_TX_PIN 17

  const uint8_t MOTOR_PWM_CHANNEL_A = 0;
  const uint8_t MOTOR_PWM_CHANNEL_B = 1;
  const uint8_t BUZZER_PWM_CHANNEL = 2;

#else

  // خريطة Arduino Uno R3. D9 مخصص لصوت Timer1؛ لذلك ENA/ENB هما D5/D6.
  #define ENA_PIN 5
  #define ENB_PIN 6
  #define IN1_PIN 7
  #define IN2_PIN 8
  #define IN3_PIN 10
  #define IN4_PIN A0

  #define LED_RED_1 11
  #define LED_RED_2 12
  #define LED_GREEN_1 13
  #define LED_GREEN_2 4

  #define BUZZER_PIN 9
  #define POT_PIN A2
  #define TRIG_PIN 2
  #define ECHO_PIN 3
  #define IR_PIN A1
  #define MPU_SDA_PIN A4
  #define MPU_SCL_PIN A5

#endif

// عكس قطبية القناتين كما طلبت؛ يمكن جعل أي قيمة false بعد اختبار العجلات مرفوعة.
const bool REVERSE_LEFT_MOTOR = true;
const bool REVERSE_RIGHT_MOTOR = true;

const uint16_t DISTANCE_STOP_CM = 15;
const uint16_t TURN_45_DURATION_MS = 200;
const uint16_t TILT_PULSE_DURATION_MS = 150;
const uint16_t SERIAL_WATCHDOG_TIMEOUT_MS = 350;
const uint8_t I2C_ADDRESS_MPU6050 = 0x68;

char globalCommand = 'S';
double globalPitchAngle = 0.0;
int globalSpeedLevel = 4;
int currentPWM = 118;
long globalDistanceCM = 999;
bool distanceReadingValid = false;
bool pitchReadingValid = false;
bool obstacleStopReported = false;
char timedActionCommand = 'S';
bool timedActionActive = false;
unsigned long timedActionDeadline = 0;

bool communicationWatchdogArmed = false;
unsigned long lastCommunicationHeartbeat = 0;

struct ToneStep
{
  uint16_t frequency;
  uint16_t durationMs;
};

const ToneStep *activeTonePattern = nullptr;
uint8_t activeToneCount = 0;
uint8_t activeToneIndex = 0;
unsigned long activeToneStartedAt = 0;
unsigned long lastPotentiometerReadAt = 0;
uint16_t currentToneFrequency = 0;
uint8_t buzzerVolumePercent = 25;

#if defined(ROBOT_PLATFORM_ESP32)
BluetoothSerial SerialBT;
#endif

// ==========================================================
// 🧭 [الجزء 2: نظام حساس الميل MPU6050]
// ==========================================================

void initMPU6050 ( )
{

#if defined(ROBOT_PLATFORM_ESP32)
  Wire.begin ( MPU_SDA_PIN , MPU_SCL_PIN );
  Wire.setTimeOut ( 50 );
#else
  Wire.begin ( );
  Wire.setWireTimeout ( 25000UL , true );
#endif

  Wire.beginTransmission ( I2C_ADDRESS_MPU6050 );
  Wire.write ( 0x6B );
  Wire.write ( 0x00 );
  uint8_t result = Wire.endTransmission ( true );
  pitchReadingValid = result == 0;

}

void updatePitchAngle ( )
{

  Wire.beginTransmission ( I2C_ADDRESS_MPU6050 );
  Wire.write ( 0x3B );
  if ( Wire.endTransmission ( false ) != 0 )
  {
    pitchReadingValid = false;
    return;
  }

  uint8_t received = Wire.requestFrom ( ( uint8_t ) I2C_ADDRESS_MPU6050 , ( uint8_t ) 2 , ( uint8_t ) true );
  if ( received < 2 || Wire.available ( ) < 2 )
  {
    while ( Wire.available ( ) > 0 ) Wire.read ( );
    pitchReadingValid = false;
    return;
  }

  int16_t rawAccelX = ( ( uint16_t ) Wire.read ( ) << 8 ) | ( uint8_t ) Wire.read ( );
  double rawAngle = ( ( double ) rawAccelX / 16384.0 ) * 90.0;
  globalPitchAngle = ( 0.8 * globalPitchAngle ) + ( 0.2 * rawAngle );
  pitchReadingValid = true;

}

// ==========================================================
// 📏 [الجزء 3: HC-SR04 ومستقبل IR]
// ==========================================================

void initSensors ( )
{

  pinMode ( TRIG_PIN , OUTPUT );
  pinMode ( ECHO_PIN , INPUT );
  pinMode ( IR_PIN , INPUT );
  digitalWrite ( TRIG_PIN , LOW );

}

void updateDistance ( )
{

  digitalWrite ( TRIG_PIN , LOW );
  delayMicroseconds ( 2 );
  digitalWrite ( TRIG_PIN , HIGH );
  delayMicroseconds ( 10 );
  digitalWrite ( TRIG_PIN , LOW );

  unsigned long duration = pulseIn ( ECHO_PIN , HIGH , 25000UL );
  if ( duration == 0 )
  {
    globalDistanceCM = 999;
    distanceReadingValid = false;
  }
  else
  {
    globalDistanceCM = ( long ) ( duration * 0.0343 / 2.0 );
    distanceReadingValid = true;
  }

}

// ==========================================================
// 🚗 [الجزء 4: L298N واتجاه المحركات والسرعة]
// ==========================================================

void initMotorPWM ( )
{

#if defined(ROBOT_PLATFORM_ESP32)
  pinMode ( IN1_PIN , OUTPUT );
  pinMode ( IN2_PIN , OUTPUT );
  pinMode ( IN3_PIN , OUTPUT );
  pinMode ( IN4_PIN , OUTPUT );

  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach ( ENA_PIN , 20000 , 8 );
    ledcAttach ( ENB_PIN , 20000 , 8 );
  #else
    ledcSetup ( MOTOR_PWM_CHANNEL_A , 20000 , 8 );
    ledcSetup ( MOTOR_PWM_CHANNEL_B , 20000 , 8 );
    ledcAttachPin ( ENA_PIN , MOTOR_PWM_CHANNEL_A );
    ledcAttachPin ( ENB_PIN , MOTOR_PWM_CHANNEL_B );
  #endif
#else
  pinMode ( ENA_PIN , OUTPUT );
  pinMode ( ENB_PIN , OUTPUT );
  pinMode ( IN1_PIN , OUTPUT );
  pinMode ( IN2_PIN , OUTPUT );
  pinMode ( IN3_PIN , OUTPUT );
  pinMode ( IN4_PIN , OUTPUT );
#endif

}

void setMotorSpeeds ( int leftPWM , int rightPWM )
{

  leftPWM = constrain ( leftPWM , 0 , 255 );
  rightPWM = constrain ( rightPWM , 0 , 255 );

#if defined(ROBOT_PLATFORM_ESP32)
  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite ( ENA_PIN , leftPWM );
    ledcWrite ( ENB_PIN , rightPWM );
  #else
    ledcWrite ( MOTOR_PWM_CHANNEL_A , leftPWM );
    ledcWrite ( MOTOR_PWM_CHANNEL_B , rightPWM );
  #endif
#else
  analogWrite ( ENA_PIN , leftPWM );
  analogWrite ( ENB_PIN , rightPWM );
#endif

}

void setLeftDirection ( bool forward )
{

  bool electricalForward = forward ^ REVERSE_LEFT_MOTOR;
  digitalWrite ( IN1_PIN , electricalForward ? HIGH : LOW );
  digitalWrite ( IN2_PIN , electricalForward ? LOW : HIGH );

}

void setRightDirection ( bool forward )
{

  // التوصيل الأصلي للقناة اليمنى كان معكوسًا ميكانيكيًا عن اليسرى.
  bool electricalForward = forward ^ REVERSE_RIGHT_MOTOR;
  digitalWrite ( IN3_PIN , electricalForward ? LOW : HIGH );
  digitalWrite ( IN4_PIN , electricalForward ? HIGH : LOW );

}

void stopLeftChannel ( )
{

  digitalWrite ( IN1_PIN , LOW );
  digitalWrite ( IN2_PIN , LOW );

}

void stopRightChannel ( )
{

  digitalWrite ( IN3_PIN , LOW );
  digitalWrite ( IN4_PIN , LOW );

}

void driveForwardAtPWM ( int pwm )
{

  setLeftDirection ( true );
  setRightDirection ( true );
  setMotorSpeeds ( pwm , pwm );

}

void driveBackwardAtPWM ( int pwm )
{

  setLeftDirection ( false );
  setRightDirection ( false );
  setMotorSpeeds ( pwm , pwm );

}

void driveForward ( )
{

  driveForwardAtPWM ( currentPWM );

}

void driveBackward ( )
{

  driveBackwardAtPWM ( currentPWM );

}

void spinCounterClockwise ( )
{

  setLeftDirection ( false );
  setRightDirection ( true );
  setMotorSpeeds ( currentPWM , currentPWM );

}

void spinClockwise ( )
{

  setLeftDirection ( true );
  setRightDirection ( false );
  setMotorSpeeds ( currentPWM , currentPWM );

}

void runRightMotorOnly ( )
{

  stopLeftChannel ( );
  setRightDirection ( true );
  setMotorSpeeds ( 0 , currentPWM );

}

void runLeftMotorOnly ( )
{

  setLeftDirection ( true );
  stopRightChannel ( );
  setMotorSpeeds ( currentPWM , 0 );

}

void stopMotors ( )
{

  stopLeftChannel ( );
  stopRightChannel ( );
  setMotorSpeeds ( 0 , 0 );

}

// ==========================================================
// 📡 [الجزء 5: Serial وBluetooth والـ watchdog]
// ==========================================================

void reportText ( const char *message )
{

  Serial.println ( message );
#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_STANDALONE)
  SerialBT.println ( message );
#endif

}

void reportReceivedCommand ( char command )
{

  Serial.print ( "Received: " );
  Serial.println ( command );
#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_STANDALONE)
  SerialBT.print ( "Received: " );
  SerialBT.println ( command );
#endif

}

void reportSpeedLevel ( )
{

  Serial.print ( "SPEED_LEVEL=" );
  Serial.print ( globalSpeedLevel );
  Serial.print ( " PWM=" );
  Serial.println ( currentPWM );
#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_STANDALONE)
  SerialBT.print ( "SPEED_LEVEL=" );
  SerialBT.print ( globalSpeedLevel );
  SerialBT.print ( " PWM=" );
  SerialBT.println ( currentPWM );
#endif

}

void initCommunication ( )
{

#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_STANDALONE)
  Serial.begin ( 115200 );
  SerialBT.begin ( "Robot_Motion_Control" );
  reportText ( "ESP32 standalone ready: Bluetooth SPP, 9600 command stream." );
#elif defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_BRIDGE)
  Serial.begin ( 115200 );
  Serial2.begin ( 9600 , SERIAL_8N1 , ESP32_LINK_RX_PIN , ESP32_LINK_TX_PIN );
  SerialBT.begin ( "Robot_Motion_Bridge" );
  Serial.println ( "ESP32 Bluetooth-to-UART bridge ready." );
#else
  Serial.begin ( 9600 );
#endif

}

void processIncomingCommand ( char incoming );

void serviceESP32Bridge ( )
{

#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_BRIDGE)
  while ( SerialBT.available ( ) > 0 )
  {
    int incoming = SerialBT.read ( );
    if ( incoming >= 0 && incoming != '\r' && incoming != '\n' )
    {
      Serial2.write ( ( uint8_t ) incoming );
    }
  }

  while ( Serial2.available ( ) > 0 )
  {
    int outgoing = Serial2.read ( );
    if ( outgoing >= 0 )
    {
      SerialBT.write ( ( uint8_t ) outgoing );
    }
  }
#endif

}

// ==========================================================
// 🎵 [الجزء 6: البازر والأنماط ومقاومة التحكم بالصوت]
// ==========================================================

void initBuzzerPWM ( )
{

  pinMode ( BUZZER_PIN , OUTPUT );
#if defined(ROBOT_PLATFORM_ESP32)
  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcAttach ( BUZZER_PIN , 800 , 10 );
    ledcWrite ( BUZZER_PIN , 0 );
  #else
    ledcSetup ( BUZZER_PWM_CHANNEL , 800 , 10 );
    ledcAttachPin ( BUZZER_PIN , BUZZER_PWM_CHANNEL );
    ledcWrite ( BUZZER_PWM_CHANNEL , 0 );
  #endif
#else
  TCCR1A = 0;
  TCCR1B = 0;
  digitalWrite ( BUZZER_PIN , LOW );
#endif

}

void stopBuzzer ( )
{

  currentToneFrequency = 0;
#if defined(ROBOT_PLATFORM_ESP32)
  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite ( BUZZER_PIN , 0 );
  #else
    ledcWrite ( BUZZER_PWM_CHANNEL , 0 );
  #endif
#else
  TCCR1A = 0;
  TCCR1B = 0;
  digitalWrite ( BUZZER_PIN , LOW );
#endif

}

void writeBuzzerDuty ( )
{

  if ( currentToneFrequency == 0 ) return;

#if defined(ROBOT_PLATFORM_ESP32)
  uint32_t duty = ( ( uint32_t ) buzzerVolumePercent * 1023UL ) / 100UL;
  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcWrite ( BUZZER_PIN , duty );
  #else
    ledcWrite ( BUZZER_PWM_CHANNEL , duty );
  #endif
#else
  if ( TCCR1B == 0 || ICR1 == 0 ) return;
  OCR1A = ( ( uint32_t ) ICR1 * buzzerVolumePercent ) / 100UL;
#endif

}

void setBuzzerFrequency ( uint16_t frequency )
{

  if ( frequency == 0 )
  {
    stopBuzzer ( );
    return;
  }

  currentToneFrequency = frequency;
#if defined(ROBOT_PLATFORM_ESP32)
  #if ESP_ARDUINO_VERSION_MAJOR >= 3
    ledcChangeFrequency ( BUZZER_PIN , frequency , 10 );
  #else
    ledcSetup ( BUZZER_PWM_CHANNEL , frequency , 10 );
  #endif
  writeBuzzerDuty ( );
#else
  // Timer1 Fast PWM mode 14, خرج OC1A على D9، مع Duty متغير من 0 إلى 50%.
  uint32_t top = ( F_CPU / ( 8UL * ( uint32_t ) frequency ) ) - 1UL;
  if ( top > 65535UL ) top = 65535UL;

  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1 = 0;
  ICR1 = ( uint16_t ) top;
  OCR1A = ( uint32_t ) top * buzzerVolumePercent / 100UL;
  TCCR1A = _BV ( COM1A1 ) | _BV ( WGM11 );
  TCCR1B = _BV ( WGM13 ) | _BV ( WGM12 ) | _BV ( CS11 );
#endif

}

void updatePotentiometerVolume ( )
{

  unsigned long now = millis ( );
  if ( now - lastPotentiometerReadAt < 40UL ) return;
  lastPotentiometerReadAt = now;

  int rawValue = analogRead ( POT_PIN );
#if defined(ROBOT_PLATFORM_ESP32)
  uint8_t newVolume = ( uint8_t ) map ( rawValue , 0 , 4095 , 0 , 50 );
#else
  uint8_t newVolume = ( uint8_t ) map ( rawValue , 0 , 1023 , 0 , 50 );
#endif

  if ( newVolume != buzzerVolumePercent )
  {
    buzzerVolumePercent = newVolume;
    writeBuzzerDuty ( );
  }

}

void initBuzzer ( )
{

#if defined(ROBOT_PLATFORM_ESP32)
  analogReadResolution ( 12 );
#endif
  pinMode ( POT_PIN , INPUT );
  buzzerVolumePercent = 25;
  initBuzzerPWM ( );
  lastPotentiometerReadAt = 0;

}

void startToneStep ( )
{

  if ( activeTonePattern == nullptr || activeToneIndex >= activeToneCount )
  {
    stopBuzzer ( );
    activeTonePattern = nullptr;
    activeToneCount = 0;
    activeToneIndex = 0;
    return;
  }

  ToneStep step = activeTonePattern [ activeToneIndex ];
  setBuzzerFrequency ( step.frequency );
  activeToneStartedAt = millis ( );

}

void handleHornAudio ( char action )
{

  // البازر أحادي النغمة؛ هذه أنماط تقريبية وليست تسجيلات أو أصوات آلات كاملة.
  static const ToneStep horn [] =
  {
    { 880 , 140 } , { 0 , 70 } , { 880 , 140 }
  };
  static const ToneStep modernHorn [] =
  {
    { 784 , 120 } , { 988 , 160 } , { 1175 , 220 } , { 988 , 140 }
  };
  static const ToneStep laCucaracha [] =
  {
    { 659 , 140 } , { 659 , 140 } , { 659 , 140 } , { 523 , 140 } ,
    { 659 , 140 } , { 784 , 280 } , { 784 , 280 }
  };
  static const ToneStep truckHorn [] =
  {
    { 392 , 260 } , { 0 , 80 } , { 392 , 260 } , { 330 , 360 }
  };
  static const ToneStep policeSiren [] =
  {
    { 700 , 140 } , { 1050 , 140 } , { 700 , 140 } , { 1050 , 140 } ,
    { 700 , 140 } , { 1050 , 140 } , { 700 , 140 } , { 1050 , 140 }
  };

  if ( action == 'H' )
  {
    activeTonePattern = horn;
    activeToneCount = sizeof ( horn ) / sizeof ( horn [ 0 ] );
  }
  else if ( action == '1' )
  {
    activeTonePattern = modernHorn;
    activeToneCount = sizeof ( modernHorn ) / sizeof ( modernHorn [ 0 ] );
  }
  else if ( action == '2' )
  {
    activeTonePattern = laCucaracha;
    activeToneCount = sizeof ( laCucaracha ) / sizeof ( laCucaracha [ 0 ] );
  }
  else if ( action == '3' )
  {
    activeTonePattern = truckHorn;
    activeToneCount = sizeof ( truckHorn ) / sizeof ( truckHorn [ 0 ] );
  }
  else if ( action == '4' )
  {
    activeTonePattern = policeSiren;
    activeToneCount = sizeof ( policeSiren ) / sizeof ( policeSiren [ 0 ] );
  }
  else
  {
    return;
  }

  activeToneIndex = 0;
  startToneStep ( );

}

void updateHornAudio ( )
{

  if ( activeTonePattern == nullptr ) return;
  ToneStep step = activeTonePattern [ activeToneIndex ];
  if ( millis ( ) - activeToneStartedAt < step.durationMs ) return;
  activeToneIndex++;
  startToneStep ( );

}

// ==========================================================
// 🎮 [الجزء 7: الأوامر والسرعة وحواجز السلامة]
// ==========================================================

int speedLevelToPWM ( int level )
{

  level = constrain ( level , 0 , 10 );
  if ( level == 0 ) return 0;
  return map ( level , 1 , 10 , 50 , 255 );

}

void updateSpeedLevel ( char action )
{

  if ( action == '+' )
  {
    globalSpeedLevel += 2;
  }
  else if ( action == '*' )
  {
    globalSpeedLevel = 10;
  }
  else if ( action == '-' )
  {
    globalSpeedLevel -= 2;
  }
  else if ( action == '/' )
  {
    globalSpeedLevel -= 1;
  }

  globalSpeedLevel = constrain ( globalSpeedLevel , 0 , 10 );
  currentPWM = speedLevelToPWM ( globalSpeedLevel );
  reportSpeedLevel ( );

}

void processIncomingCommand ( char incoming )
{

  if ( incoming == '\n' || incoming == '\r' ) return;
  if ( incoming == 'Z' )
  {
    lastCommunicationHeartbeat = millis ( );
    communicationWatchdogArmed = true;
    return;
  }

  char command = incoming == 'c' ? 'c' : ( char ) toupper ( ( unsigned char ) incoming );
  reportReceivedCommand ( command );

  if ( command == '+' || command == '-' || command == '*' || command == '/' )
  {
    updateSpeedLevel ( command );
    return;
  }

  if ( command == 'H' || command == '1' || command == '2' || command == '3' || command == '4' )
  {
    handleHornAudio ( command );
    return;
  }

  if ( command == '<' || command == '>' )
  {
    globalCommand = 'S';
    timedActionCommand = command;
    timedActionActive = true;
    timedActionDeadline = millis ( ) + TURN_45_DURATION_MS;
    return;
  }

  if ( command == '^' || command == 'V' )
  {
    bool pitchThresholdMet = command == '^' ? globalPitchAngle > 15.0 : globalPitchAngle < -15.0;
    bool pitchAvailable = pitchReadingValid && pitchThresholdMet;
    bool forwardPathClear = distanceReadingValid && globalDistanceCM >= DISTANCE_STOP_CM;

    if ( !pitchAvailable || ( command == '^' && !forwardPathClear ) )
    {
      reportText ( "ACTION_BLOCKED: sensor, angle, or distance interlock" );
      return;
    }

    globalCommand = 'S';
    timedActionCommand = command;
    timedActionActive = true;
    timedActionDeadline = millis ( ) + TILT_PULSE_DURATION_MS;
    return;
  }

  if ( command == 'F' || command == 'B' || command == 'L' || command == 'R' ||
       command == 'C' || command == 'c' || command == 'J' || command == 'S' )
  {
    globalCommand = command;
    timedActionActive = false;
    timedActionCommand = 'S';
    if ( command == 'S' ) stopMotors ( );
    return;
  }

  globalCommand = 'S';
  timedActionActive = false;
  timedActionCommand = 'S';
  stopMotors ( );
  reportText ( "Unknown command; stopped." );

}

void checkCommunicationWatchdog ( )
{

  if ( !communicationWatchdogArmed ) return;
  if ( millis ( ) - lastCommunicationHeartbeat <= SERIAL_WATCHDOG_TIMEOUT_MS ) return;

  communicationWatchdogArmed = false;
  globalCommand = 'S';
  timedActionActive = false;
  timedActionCommand = 'S';
  stopMotors ( );
  reportText ( "WATCHDOG: heartbeat lost; motors stopped." );

}

void fetchCommand ( )
{

#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_STANDALONE)
  while ( SerialBT.available ( ) > 0 )
  {
    processIncomingCommand ( ( char ) SerialBT.read ( ) );
  }
#endif

  while ( Serial.available ( ) > 0 )
  {
    processIncomingCommand ( ( char ) Serial.read ( ) );
  }

}

void executeControllerLogic ( )
{

  char activeCommand = globalCommand;
  if ( timedActionActive )
  {
    if ( ( long ) ( millis ( ) - timedActionDeadline ) >= 0 )
    {
      timedActionActive = false;
      timedActionCommand = 'S';
    }
    else
    {
      activeCommand = timedActionCommand;
    }
  }

  bool forwardCommand = activeCommand == 'F' || activeCommand == 'J' || activeCommand == '^';
  if ( forwardCommand && ( !distanceReadingValid || globalDistanceCM < DISTANCE_STOP_CM ) )
  {
    stopMotors ( );
    if ( !obstacleStopReported )
    {
      reportText ( distanceReadingValid ? "MOTION_BLOCKED: obstacle under 15 cm" : "MOTION_BLOCKED: distance sensor invalid" );
      obstacleStopReported = true;
    }
    return;
  }

  obstacleStopReported = false;
  if ( activeCommand == 'S' || globalSpeedLevel == 0 )
  {
    stopMotors ( );
    return;
  }

  if ( activeCommand == 'F' ) driveForward ( );
  else if ( activeCommand == 'B' ) driveBackward ( );
  else if ( activeCommand == 'L' ) runLeftMotorOnly ( );
  else if ( activeCommand == 'R' ) runRightMotorOnly ( );
  else if ( activeCommand == 'C' ) spinCounterClockwise ( );
  else if ( activeCommand == 'c' ) spinClockwise ( );
  else if ( activeCommand == 'J' ) driveForwardAtPWM ( 100 );
  else if ( activeCommand == '^' ) driveForwardAtPWM ( 255 );
  else if ( activeCommand == 'V' ) driveBackwardAtPWM ( 255 );
  else if ( activeCommand == '>' ) spinClockwise ( );
  else if ( activeCommand == '<' ) spinCounterClockwise ( );
  else stopMotors ( );

}

// ==========================================================
// 💡 [الجزء 8: مؤشرات الحركة والاتجاه]
// ==========================================================

void initLEDs ( )
{

  pinMode ( LED_RED_1 , OUTPUT );
  pinMode ( LED_RED_2 , OUTPUT );
  pinMode ( LED_GREEN_1 , OUTPUT );
  pinMode ( LED_GREEN_2 , OUTPUT );
  digitalWrite ( LED_RED_1 , LOW );
  digitalWrite ( LED_RED_2 , LOW );
  digitalWrite ( LED_GREEN_1 , LOW );
  digitalWrite ( LED_GREEN_2 , LOW );

}

void updateLEDIndicators ( )
{

  char activeCommand = timedActionActive ? timedActionCommand : globalCommand;
  bool forward = activeCommand == 'F' || activeCommand == 'J' || activeCommand == '^';
  bool backward = activeCommand == 'B' || activeCommand == 'V';
  bool turning = activeCommand == 'L' || activeCommand == 'R' || activeCommand == 'C' ||
                 activeCommand == 'c' || activeCommand == '<' || activeCommand == '>';

  digitalWrite ( LED_GREEN_1 , forward || turning ? HIGH : LOW );
  digitalWrite ( LED_GREEN_2 , forward || turning ? HIGH : LOW );
  digitalWrite ( LED_RED_1 , backward ? HIGH : LOW );
  digitalWrite ( LED_RED_2 , backward ? HIGH : LOW );

}

// ==========================================================
// ⚙️ [الجزء 9: التهيئة والحلقة الرئيسية]
// ==========================================================

void setup ( )
{

  initCommunication ( );

#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_BRIDGE)
  // وضع الجسر لا يشغّل المحركات؛ الأردوينو هو المتحكم الرئيسي.
  return;
#else
  initMotorPWM ( );
  initSensors ( );
  initMPU6050 ( );
  initBuzzer ( );
  initLEDs ( );
  stopMotors ( );
  currentPWM = speedLevelToPWM ( globalSpeedLevel );
#endif

}

void loop ( )
{

#if defined(ROBOT_PLATFORM_ESP32) && defined(ROBOT_ROLE_ESP32_BRIDGE)
  serviceESP32Bridge ( );
  delay ( 1 );
#else
  updatePitchAngle ( );
  updateDistance ( );
  fetchCommand ( );
  checkCommunicationWatchdog ( );
  updatePotentiometerVolume ( );
  updateHornAudio ( );
  executeControllerLogic ( );
  updateLEDIndicators ( );
  delay ( 10 );
#endif

}
