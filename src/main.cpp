#include <Arduino.h>
#include <Wire.h>

#ifdef ESP32
  #include <WiFi.h>
  #include <BluetoothSerial.h>
  BluetoothSerial SerialBT ;
#endif





// ==========================================================
// 📌 [الجزء 1: المتغيرات العامة وتعاريف الأطراف - PINS & GLOBALS]
// ==========================================================

#define ENA_PIN  5
#define IN1_PIN  6
#define IN2_PIN  7
#define IN3_PIN  8
#define IN4_PIN  9
#define ENB_PIN  10

#define LED_1    11
#define LED_2    12
#define LED_3    13
#define LED_4    4

// طرف البزر
#define BUZZER_PIN A0

// أطراف حساس الحوادث والمستقبل
#define TRIG_PIN 2
#define ECHO_PIN 3
#define IR_PIN   A1

// متغيرات الربط بين الأجزاء
char globalCommand = 'S' ;
double globalPitchAngle = 0.0 ;
int globalSpeedLevel = 4 ;
int currentPWM = 100 ;
long globalDistanceCM = 999 ;





// ==========================================================
// 🧭 [الجزء 2: نظام حساس زاوية الميل MPU6050]
// ==========================================================

void initMPU6050 ( )
{

  Wire.begin ( ) ;

  // [حل مشكلة اللاج والتجمد 1] تحديد وقت أقصى (Timeout) لانتظار الحساس لمنع حلقة التعليق المفرغة
  Wire.setWireTimeout ( 25000 , true ) ;

  Wire.beginTransmission ( 0x68 ) ;
  Wire.write ( 0x6B ) ;
  Wire.write ( 0 ) ;
  Wire.endTransmission ( true ) ;

}


void updatePitchAngle ( )
{

  Wire.beginTransmission ( 0x68 ) ;
  Wire.write ( 0x3B ) ;
  Wire.endTransmission ( false ) ;
  Wire.requestFrom ( 0x68 , 2 , true ) ;

  int16_t rawAccelY = ( Wire.read ( ) << 8 | Wire.read ( ) ) ;

  double rawAngle = ( ( double ) rawAccelY / 16384.0 ) * 90.0 ;

  globalPitchAngle = ( 0.8 * globalPitchAngle ) + ( 0.2 * rawAngle ) ;

}





// ==========================================================
// 📏 [الجزء 3: نظام حساس المسافة الألتراسونيك ومستقبل IR]
// ==========================================================

void initSensors ( )
{

  pinMode ( TRIG_PIN , OUTPUT ) ;
  pinMode ( ECHO_PIN , INPUT ) ;
  pinMode ( IR_PIN , INPUT ) ;

}


void updateDistance ( )
{

  digitalWrite ( TRIG_PIN , LOW ) ;
  delayMicroseconds ( 2 ) ;
  digitalWrite ( TRIG_PIN , HIGH ) ;
  delayMicroseconds ( 10 ) ;
  digitalWrite ( TRIG_PIN , LOW ) ;

  long duration = pulseIn ( ECHO_PIN , HIGH , 25000 ) ; // Timeout 25ms

  if ( duration == 0 )
  {
    globalDistanceCM = 999 ;
  }
  else
  {
    globalDistanceCM = duration * 0.034 / 2 ;
  }

}





// ==========================================================
// 🚗 [الجزء 4: نظام الحركة والمحركات الأساسية]
// ==========================================================

void initMotors ( )
{

  pinMode ( ENA_PIN , OUTPUT ) ;
  pinMode ( IN1_PIN , OUTPUT ) ;
  pinMode ( IN2_PIN , OUTPUT ) ;
  pinMode ( IN3_PIN , OUTPUT ) ;
  pinMode ( IN4_PIN , OUTPUT ) ;
  pinMode ( ENB_PIN , OUTPUT ) ;

}


void setMotorSpeeds ( int leftPWM , int rightPWM )
{

  analogWrite ( ENA_PIN , leftPWM ) ;
  analogWrite ( ENB_PIN , rightPWM ) ;

}


void driveForward ( )
{

  // تم عكس إشارات المحرك الأيمن (IN3, IN4) لتوحيد اتجاه الحركة للأمام
  digitalWrite ( IN1_PIN , HIGH ) ;
  digitalWrite ( IN2_PIN , LOW ) ;
  digitalWrite ( IN3_PIN , LOW ) ;
  digitalWrite ( IN4_PIN , HIGH ) ;
  setMotorSpeeds ( currentPWM , currentPWM ) ;

}


void driveBackward ( )
{

  // تم عكس إشارات المحرك الأيمن (IN3, IN4) لتوحيد اتجاه الحركة للخلف
  digitalWrite ( IN1_PIN , LOW ) ;
  digitalWrite ( IN2_PIN , HIGH ) ;
  digitalWrite ( IN3_PIN , HIGH ) ;
  digitalWrite ( IN4_PIN , LOW ) ;
  setMotorSpeeds ( currentPWM , currentPWM ) ;

}


void spinCounterClockwise ( )
{

  digitalWrite ( IN1_PIN , LOW ) ;
  digitalWrite ( IN2_PIN , HIGH ) ;
  digitalWrite ( IN3_PIN , LOW ) ;
  digitalWrite ( IN4_PIN , HIGH ) ;
  setMotorSpeeds ( currentPWM , currentPWM ) ;

}


void spinClockwise ( )
{

  digitalWrite ( IN1_PIN , HIGH ) ;
  digitalWrite ( IN2_PIN , LOW ) ;
  digitalWrite ( IN3_PIN , HIGH ) ;
  digitalWrite ( IN4_PIN , LOW ) ;
  setMotorSpeeds ( currentPWM , currentPWM ) ;

}


void runRightMotorOnly ( )
{

  digitalWrite ( IN1_PIN , LOW ) ;
  digitalWrite ( IN2_PIN , LOW ) ;
  digitalWrite ( IN3_PIN , LOW ) ;
  digitalWrite ( IN4_PIN , HIGH ) ;
  setMotorSpeeds ( 0 , currentPWM ) ;

}


void runLeftMotorOnly ( )
{

  digitalWrite ( IN1_PIN , HIGH ) ;
  digitalWrite ( IN2_PIN , LOW ) ;
  digitalWrite ( IN3_PIN , LOW ) ;
  digitalWrite ( IN4_PIN , LOW ) ;
  setMotorSpeeds ( currentPWM , 0 ) ;

}


void stopMotors ( )
{

  digitalWrite ( IN1_PIN , LOW ) ;
  digitalWrite ( IN2_PIN , LOW ) ;
  digitalWrite ( IN3_PIN , LOW ) ;
  digitalWrite ( IN4_PIN , LOW ) ;
  setMotorSpeeds ( 0 , 0 ) ;

}





// ==========================================================
// 📡 [الجزء 5: نظام الاتصالات واستقبال أوامر اللابتوب]
// ==========================================================

void initCommunication ( )
{

  Serial.begin ( 9600 ) ;

  #ifdef ESP32
    SerialBT.begin ( "Robot_ESP32_Control" ) ;
  #endif

}


void fetchCommand ( )
{

  #ifdef ESP32
    while ( SerialBT.available ( ) > 0 )
    {
      char c = SerialBT.read ( ) ;
      if ( c != '\n' && c != '\r' )
      {
        globalCommand = toupper ( c ) ;
        Serial.print ( "Received: " ) ;
        Serial.println ( globalCommand ) ;
      }
    }
  #endif

  while ( Serial.available ( ) > 0 )
  {
    char c = Serial.read ( ) ;
    if ( c != '\n' && c != '\r' )
    {
      if ( c == 'c' )
      {
        globalCommand = 'c' ;
      }
      else
      {
        globalCommand = toupper ( c ) ;
      }

      // إعادة إظهار الحرف المستلم في الـ Terminal
      Serial.print ( "Received: " ) ;
      Serial.println ( globalCommand ) ;
    }
  }

}





// ==========================================================
// 🎵 [الجزء 6: نظام البزر والأصوات الموسيقية للسيارة]
// ==========================================================

void initBuzzer ( )
{

  pinMode ( BUZZER_PIN , OUTPUT ) ;

}


void handleHornAudio ( char action )
{

  if ( action == 'H' )
  {
    tone ( BUZZER_PIN , 1000 , 150 ) ;
  }
  else if ( action == '1' )
  {
    tone ( BUZZER_PIN , 500 , 200 ) ;
    delay ( 200 ) ;
    tone ( BUZZER_PIN , 650 , 300 ) ;
  }
  else if ( action == '2' )
  {
    tone ( BUZZER_PIN , 523 , 100 ) ; delay ( 120 ) ;
    tone ( BUZZER_PIN , 523 , 100 ) ; delay ( 120 ) ;
    tone ( BUZZER_PIN , 523 , 100 ) ; delay ( 120 ) ;
    tone ( BUZZER_PIN , 698 , 300 ) ; delay ( 300 ) ;
    tone ( BUZZER_PIN , 880 , 300 ) ;
  }
  else if ( action == '3' )
  {
    tone ( BUZZER_PIN , 200 , 400 ) ;
  }
  else if ( action == '4' )
  {
    for ( int i = 0 ; i < 3 ; i++ )
    {
      tone ( BUZZER_PIN , 800 , 150 ) ;
      delay ( 150 ) ;
      tone ( BUZZER_PIN , 1200 , 150 ) ;
      delay ( 150 ) ;
    }
  }

}





// ==========================================================
// 🎮 [الجزء 7: نظام معالجة الأوامر والتحكم الذكي]
// ==========================================================

void updateSpeedLevel ( char action )
{

  if ( action == '+' )
  {
    globalSpeedLevel += 2 ;
  }
  else if ( action == '*' )
  {
    globalSpeedLevel = 10 ;
  }
  else if ( action == '-' )
  {
    globalSpeedLevel -= 2 ;
  }
  else if ( action == '/' )
  {
    globalSpeedLevel -= 1 ;
  }

  if ( globalSpeedLevel > 10 ) globalSpeedLevel = 10 ;
  if ( globalSpeedLevel < 1 )  globalSpeedLevel = 1 ;

  currentPWM = map ( globalSpeedLevel , 1 , 10 , 50 , 255 ) ;

}


void executeControllerLogic ( )
{

  updateSpeedLevel ( globalCommand ) ;
  handleHornAudio ( globalCommand ) ;

  // حماية التوقف التلقائي عند الاقتراب من عائق (< 15 سم) عند الحركة للأمام
  if ( globalDistanceCM < 15 && ( globalCommand == 'F' || globalCommand == 'J' || globalCommand == '^' ) )
  {
    stopMotors ( ) ;
    return ;
  }

  if ( globalCommand == 'J' )
  {
    currentPWM = 100 ;
    driveForward ( ) ;
    return ;
  }

  if ( globalCommand == 'R' )
  {
    runRightMotorOnly ( ) ;
    return ;
  }
  if ( globalCommand == 'L' )
  {
    runLeftMotorOnly ( ) ;
    return ;
  }

  if ( globalCommand == '>' )
  {
    spinClockwise ( ) ;
    delay ( 200 ) ;
    stopMotors ( ) ;
    return ;
  }
  if ( globalCommand == '<' )
  {
    spinCounterClockwise ( ) ;
    delay ( 200 ) ;
    stopMotors ( ) ;
    return ;
  }

  if ( globalCommand == '^' )
  {
    if ( globalPitchAngle > 15.0 )
    {
      currentPWM = 255 ;
      driveForward ( ) ;
      delay ( 150 ) ;
      stopMotors ( ) ;
    }
    return ;
  }

  if ( globalCommand == 'V' )
  {
    if ( globalPitchAngle < -15.0 )
    {
      currentPWM = 255 ;
      driveBackward ( ) ;
      delay ( 150 ) ;
      stopMotors ( ) ;
    }
    return ;
  }


  if ( globalCommand == 'F' )
  {
    driveForward ( ) ;
  }
  else if ( globalCommand == 'B' )
  {
    driveBackward ( ) ;
  }
  else if ( globalCommand == 'C' )
  {
    spinCounterClockwise ( ) ;
  }
  else if ( globalCommand == 'c' )
  {
    spinClockwise ( ) ;
  }
  else
  {
    stopMotors ( ) ;
  }

}





// ==========================================================
// 💡 [الجزء 8: نظام مؤشرات الليدات]
// ==========================================================

void initLEDs ( )
{

  pinMode ( LED_1 , OUTPUT ) ;
  pinMode ( LED_2 , OUTPUT ) ;
  pinMode ( LED_3 , OUTPUT ) ;
  pinMode ( LED_4 , OUTPUT ) ;

}


void flashLEDs ( )
{

  if ( globalSpeedLevel >= 8 )
  {
    digitalWrite ( LED_1 , HIGH ) ;
    digitalWrite ( LED_4 , HIGH ) ;
  }
  else
  {
    digitalWrite ( LED_1 , LOW ) ;
    digitalWrite ( LED_4 , LOW ) ;
  }

}





// ==========================================================
// ⚙️ [الجزء 9: الحلقة الرئيسية والتهيئة - MAIN SETUP & LOOP]
// ==========================================================

void setup ( )
{

  initCommunication ( ) ;
  initMPU6050 ( ) ;
  initSensors ( ) ;
  initMotors ( ) ;
  initBuzzer ( ) ;
  initLEDs ( ) ;

  stopMotors ( ) ;

}


void loop ( )
{

  updatePitchAngle ( ) ;

  updateDistance ( ) ;

  fetchCommand ( ) ;

  executeControllerLogic ( ) ;

  flashLEDs ( ) ;

  delay ( 20 ) ;

}
