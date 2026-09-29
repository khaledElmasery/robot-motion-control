#include <Arduino.h>
#include <Wire.h>
#include <PID_v1.h>

#ifdef ESP32
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>
#endif

#define MPU_ADDR 0x68
#define COMMAND_TIMEOUT_MS 1000UL
#define OBSTACLE_CM 100.0f

#ifdef ARDUINO
const uint8_t ENA_PIN=5,IN1_PIN=6,IN2_PIN=7,IN3_PIN=8,IN4_PIN=9,ENB_PIN=10;
const uint8_t IR_PIN=3,LED_1=11,LED_2=12,LED_3=13,LED_4=4,TRIG_PIN=A0,ECHO_PIN=A1;
#endif

#ifdef ESP32
const uint8_t SDA_PIN=21,SCL_PIN=22,IN1_PIN=32,IN2_PIN=33,IN3_PIN=25,IN4_PIN=26;
const uint8_t ENA_PIN=27,ENB_PIN=14,IR_PIN=2,MODE_PIN=35,LED_1=4,LED_2=16,LED_3=17,LED_4=23,TRIG_PIN=5,ECHO_PIN=34;
const char* WIFI_SSID="BalanceBot";
const char* WIFI_PASSWORD="change-this-password";
const char* CLOUD_BASE_URL="http://192.168.1.10:8080";
const char* CONTROL_TOKEN="change-me";
HardwareSerial Bridge(2);
WebServer localServer(80);
bool bridgeMode=false;
#endif

double input=0,output=0,setpoint=0;
PID balancePID(&input,&output,&setpoint,22.0,140.0,1.5,DIRECT);
char command='S';
uint32_t lastCommand=0,lastImu=0,lastTelemetry=0,lastCloud=0,lastWifiAttempt=0;
float angle=0,telemetryAngle=0,telemetryOutput=0,telemetryDistance=-1;
char telemetryCommand='S';
bool imuReady=false;

bool allowed(char c){return c=='F'||c=='B'||c=='L'||c=='R'||c=='S';}
void acceptCommand(char c){c=toupper(c);if(allowed(c)){command=c;lastCommand=millis();}}

#ifdef ESP32
void routeCommand(char c){acceptCommand(c);if(bridgeMode){Bridge.println(c);}}
#else
void routeCommand(char c){acceptCommand(c);}
#endif

void setup(){
#ifdef ARDUINO
  Serial.begin(115200);
  Wire.begin();
#endif
#ifdef ESP32
  Serial.begin(115200);
  Wire.begin(SDA_PIN,SCL_PIN);
  Bridge.begin(115200,SERIAL_8N1,18,19);
  pinMode(MODE_PIN,INPUT);
  bridgeMode=digitalRead(MODE_PIN)==LOW;
#endif
  initMpu();
  pinMode(ENA_PIN,OUTPUT);pinMode(IN1_PIN,OUTPUT);pinMode(IN2_PIN,OUTPUT);pinMode(IN3_PIN,OUTPUT);pinMode(IN4_PIN,OUTPUT);pinMode(ENB_PIN,OUTPUT);
  pinMode(LED_1,OUTPUT);pinMode(LED_2,OUTPUT);pinMode(LED_3,OUTPUT);pinMode(LED_4,OUTPUT);pinMode(TRIG_PIN,OUTPUT);pinMode(ECHO_PIN,INPUT);pinMode(IR_PIN,INPUT);
#ifdef ESP32
  ledcAttach(ENA_PIN,20000,8);ledcAttach(ENB_PIN,20000,8);startLocalServer();connectCloud();
#endif
  balancePID.SetOutputLimits(-255,255);balancePID.SetSampleTime(10);balancePID.SetMode(AUTOMATIC);stopMotors();lastCommand=millis();
}

void loop(){
#ifdef ESP32
  localServer.handleClient();
  if(bridgeMode){
    readBridgeTelemetry();
    if(millis()-lastCloud>150) fetchCloudCommand();
    if(millis()-lastTelemetry>150){lastTelemetry=millis();postBridgeTelemetry();}
    maintainCloud();
    return;
  }
  readCommandSerial(Serial);
  if(millis()-lastCloud>150) fetchCloudCommand();
#else
  readCommandSerial(Serial);
#endif
  uint32_t now=millis();
  if(now-lastCommand>COMMAND_TIMEOUT_MS)command='S';
  if(now-lastImu>=5){float dt=(now-lastImu)/1000.0f;lastImu=now;input=readAngle(dt);}
  float distance=readDistance();
  bool blocked=distance>0&&distance<OBSTACLE_CM&&command=='F';
  setpoint=blocked?-1.0:(command=='F'?3.0:(command=='B'?-3.0:0.0));
  if(fabs(input)>35){stopMotors();output=0;}else{balancePID.Compute();drive(output,command);}
  indicators(input,command,blocked,now);
  if(now-lastTelemetry>=100){lastTelemetry=now;publishLocalTelemetry(distance);}
}

void readCommandSerial(Stream &s){while(s.available()){char c=toupper(s.read());if(allowed(c))routeCommand(c);}}

void initMpu(){Wire.beginTransmission(MPU_ADDR);Wire.write(0x6B);Wire.write(0);imuReady=Wire.endTransmission(true)==0;Wire.beginTransmission(MPU_ADDR);Wire.write(0x1B);Wire.write(0);Wire.endTransmission(true);}
float readAngle(float dt){if(!imuReady)return 0;Wire.beginTransmission(MPU_ADDR);Wire.write(0x3B);Wire.endTransmission(false);if(Wire.requestFrom(MPU_ADDR,(uint8_t)14,true)!=14)return angle;int16_t ax=Wire.read()<<8|Wire.read();Wire.read();Wire.read();int16_t az=Wire.read()<<8|Wire.read();Wire.read();Wire.read();int16_t gy=Wire.read()<<8|Wire.read();Wire.read();Wire.read();float accel=atan2((float)ax,(float)az)*57.2958f;angle=.98f*(angle+(gy/131.0f)*dt)+.02f*accel;return angle;}
float readDistance(){digitalWrite(TRIG_PIN,LOW);delayMicroseconds(2);digitalWrite(TRIG_PIN,HIGH);delayMicroseconds(10);digitalWrite(TRIG_PIN,LOW);unsigned long us=pulseIn(ECHO_PIN,HIGH,18000);return us?us*.0343f/2.0f:-1;}
void drive(double v,char c){if(c=='L')v-=35;if(c=='R')v+=35;int p=constrain((int)fabs(v),0,255);bool f=v>0;if(v==0){digitalWrite(IN1_PIN,0);digitalWrite(IN2_PIN,0);digitalWrite(IN3_PIN,0);digitalWrite(IN4_PIN,0);}else{digitalWrite(IN1_PIN,f);digitalWrite(IN2_PIN,!f);digitalWrite(IN3_PIN,f);digitalWrite(IN4_PIN,!f);}
#ifdef ESP32
  ledcWrite(ENA_PIN,p);ledcWrite(ENB_PIN,p);
#else
  analogWrite(ENA_PIN,p);analogWrite(ENB_PIN,p);
#endif
}
void stopMotors(){
#ifdef ESP32
  ledcWrite(ENA_PIN,0);ledcWrite(ENB_PIN,0);
#else
  analogWrite(ENA_PIN,0);analogWrite(ENB_PIN,0);
#endif
  digitalWrite(IN1_PIN,0);digitalWrite(IN2_PIN,0);digitalWrite(IN3_PIN,0);digitalWrite(IN4_PIN,0);
}
void indicators(float a,char c,bool blocked,uint32_t n){if(fabs(a)>35||blocked){bool x=(n/100)%2;digitalWrite(LED_1,x);digitalWrite(LED_2,x);digitalWrite(LED_3,x);digitalWrite(LED_4,x);return;}uint8_t s=(n/120)%4,p[4]={LED_1,LED_2,LED_3,LED_4};if(c=='B')s=3-s;for(uint8_t i=0;i<4;i++)digitalWrite(p[i],(c=='F'||c=='B')?i==s:(i==1||i==2)&&fabs(a)<2);}

void publishLocalTelemetry(float d){String t="TEL angle="+String(input,2)+" output="+String(output,2)+" distance="+String(d,1)+" command="+String(command)+" mode=arduino";
#ifdef ARDUINO
  Serial.println(t);
#endif
#ifdef ESP32
  Serial.println(t);
  if(WiFi.status()==WL_CONNECTED)postTelemetry(input,output,d,command,"standalone");
#endif
}

#ifdef ESP32
void startLocalServer(){localServer.on("/cmd",HTTP_GET,[](){if(localServer.hasArg("c"))routeCommand(localServer.arg("c")[0]);localServer.send(200,"text/plain","OK");});localServer.on("/telemetry",HTTP_GET,[](){localServer.send(200,"application/json",telemetryJson(telemetryAngle,telemetryOutput,telemetryDistance,telemetryCommand,bridgeMode?"bridge":"standalone"));});localServer.begin();}
String telemetryJson(float a,float o,float d,char c,const char* mode){return String("{\"angle\":")+String(a,2)+",\"output\":"+String(o,2)+",\"distance\":"+String(d,1)+",\"command\":\""+String(c)+"\",\"mode\":\""+mode+"\",\"uptime\":"+String(millis())+"}";}
void connectCloud(){WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);lastWifiAttempt=millis();uint32_t start=millis();while(WiFi.status()!=WL_CONNECTED&&millis()-start<8000)delay(50);if(WiFi.status()!=WL_CONNECTED){WiFi.mode(WIFI_AP);WiFi.softAP("BalanceBot-Setup","balance123");}}
void maintainCloud(){if(WiFi.status()==WL_CONNECTED)return;if(millis()-lastWifiAttempt<10000)return;lastWifiAttempt=millis();WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);if(WiFi.status()!=WL_CONNECTED){WiFi.mode(WIFI_AP);WiFi.softAP("BalanceBot-Setup","balance123");}}
void fetchCloudCommand(){lastCloud=millis();if(WiFi.status()!=WL_CONNECTED)return;HTTPClient h;h.begin(String(CLOUD_BASE_URL)+"/api/device/command");h.addHeader("Authorization",String("Bearer ")+CONTROL_TOKEN);int code=h.GET();if(code==200){String s=h.getString();int i=s.indexOf("\"command\":\"");if(i>=0)routeCommand(s.charAt(i+11));}h.end();}
void postTelemetry(float a,float o,float d,char c,const char* mode){HTTPClient h;h.begin(String(CLOUD_BASE_URL)+"/api/telemetry");h.addHeader("Content-Type","application/json");h.addHeader("Authorization",String("Bearer ")+CONTROL_TOKEN);h.POST(telemetryJson(a,o,d,c,mode));h.end();}
void readBridgeTelemetry(){while(Bridge.available()){String line=Bridge.readStringUntil('\n');int a=line.indexOf("angle=");int o=line.indexOf("output=");int d=line.indexOf("distance=");int c=line.indexOf("command=");if(a>=0)telemetryAngle=line.substring(a+6).toFloat();if(o>=0)telemetryOutput=line.substring(o+7).toFloat();if(d>=0)telemetryDistance=line.substring(d+9).toFloat();if(c>=0&&c+8<line.length())telemetryCommand=line.charAt(c+8);}}
void postBridgeTelemetry(){if(WiFi.status()==WL_CONNECTED)postTelemetry(telemetryAngle,telemetryOutput,telemetryDistance,telemetryCommand,"bridge");}
#endif
