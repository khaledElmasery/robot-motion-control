#include <Wire.h>
#include <PID_v1.h>

// Arduino Uno pinout — keep synchronized with hardware/PINOUT_AND_POWER_AR.md
const uint8_t ENA_PIN=5, IN1_PIN=6, IN2_PIN=7, IN3_PIN=8, IN4_PIN=9, ENB_PIN=10;
const uint8_t IR_PIN=3, LED_1=11, LED_2=12, LED_3=13, LED_4=4;
const uint8_t TRIG_PIN=A0, ECHO_PIN=A1;
const uint8_t MPU_ADDR=0x68;

double input=0, output=0, setpoint=0;
double Kp=22, Ki=140, Kd=1.5;
PID balancePID(&input,&output,&setpoint,Kp,Ki,Kd,DIRECT);
char command='S'; uint32_t lastCommandMs=0, lastImuMs=0, lastTelemetryMs=0;
float gyroBias=0, angle=0; bool imuReady=false;

void setup(){ Serial.begin(115200); Wire.begin(); initMpu();
  for(uint8_t p: {ENA_PIN,IN1_PIN,IN2_PIN,IN3_PIN,IN4_PIN,ENB_PIN,LED_1,LED_2,LED_3,LED_4,TRIG_PIN}) pinMode(p,OUTPUT);
  pinMode(ECHO_PIN,INPUT); pinMode(IR_PIN,INPUT); stopMotors();
  balancePID.SetOutputLimits(-255,255); balancePID.SetSampleTime(10); balancePID.SetMode(AUTOMATIC);
  lastCommandMs=millis(); Serial.println(F("READY ArduinoBalance v2"));
}
void loop(){ uint32_t now=millis(); readSerialCommand();
  if(now-lastCommandMs>1000) command='S';
  if(now-lastImuMs>=5){ float dt=(now-lastImuMs)/1000.0f; lastImuMs=now; input=readAngle(dt); }
  float distance=readDistanceCm(); bool blocked=(distance>0 && distance<100 && command=='F');
  setpoint = blocked ? -1.0 : (command=='F'?3.0:(command=='B'?-3.0:0.0));
  if(fabs(input)>35){ stopMotors(); output=0; }
  else { balancePID.Compute(); drive(output,command); }
  indicators(input,command,blocked,now);
  if(now-lastTelemetryMs>=100){ lastTelemetryMs=now; Serial.print(F("TEL angle="));Serial.print(input,2);Serial.print(F(" output="));Serial.print(output,2);Serial.print(F(" distance="));Serial.print(distance,1);Serial.print(F(" command="));Serial.println(command); }
}
void readSerialCommand(){ while(Serial.available()){ char c=toupper(Serial.read()); if(c=='F'||c=='B'||c=='L'||c=='R'||c=='S'){command=c;lastCommandMs=millis();} } }
void initMpu(){ Wire.beginTransmission(MPU_ADDR);Wire.write(0x6B);Wire.write(0);imuReady=(Wire.endTransmission(true)==0); Wire.beginTransmission(MPU_ADDR);Wire.write(0x1B);Wire.write(0);Wire.endTransmission(true); }
float readAngle(float dt){ if(!imuReady)return 0; Wire.beginTransmission(MPU_ADDR);Wire.write(0x3B);Wire.endTransmission(false); if(Wire.requestFrom(MPU_ADDR,(uint8_t)14,true)!=14)return angle; int16_t ax=Wire.read()<<8|Wire.read(); int16_t ay=Wire.read()<<8|Wire.read(); int16_t az=Wire.read()<<8|Wire.read(); Wire.read();Wire.read(); int16_t gy=Wire.read()<<8|Wire.read(); Wire.read();Wire.read(); float accel=atan2((float)ax,(float)az)*57.2958f; float gyro=(gy/131.0f)-gyroBias; angle=0.98f*(angle+gyro*dt)+0.02f*accel; return angle; }
float readDistanceCm(){ digitalWrite(TRIG_PIN,LOW);delayMicroseconds(2);digitalWrite(TRIG_PIN,HIGH);delayMicroseconds(10);digitalWrite(TRIG_PIN,LOW); unsigned long us=pulseIn(ECHO_PIN,HIGH,18000); return us?us*0.0343f/2.0f:-1; }
void drive(double v,char c){ if(c=='L')v-=35; if(c=='R')v+=35; int pwm=constrain((int)fabs(v),0,255); if(v>0){digitalWrite(IN1_PIN,HIGH);digitalWrite(IN2_PIN,LOW);digitalWrite(IN3_PIN,HIGH);digitalWrite(IN4_PIN,LOW);} else if(v<0){digitalWrite(IN1_PIN,LOW);digitalWrite(IN2_PIN,HIGH);digitalWrite(IN3_PIN,LOW);digitalWrite(IN4_PIN,HIGH);} else {digitalWrite(IN1_PIN,LOW);digitalWrite(IN2_PIN,LOW);digitalWrite(IN3_PIN,LOW);digitalWrite(IN4_PIN,LOW);} analogWrite(ENA_PIN,pwm);analogWrite(ENB_PIN,pwm); }
void stopMotors(){analogWrite(ENA_PIN,0);analogWrite(ENB_PIN,0);digitalWrite(IN1_PIN,LOW);digitalWrite(IN2_PIN,LOW);digitalWrite(IN3_PIN,LOW);digitalWrite(IN4_PIN,LOW);}
void indicators(float a,char c,bool blocked,uint32_t now){ if(fabs(a)>35||blocked){bool on=(now/100)%2;digitalWrite(LED_1,on);digitalWrite(LED_2,on);digitalWrite(LED_3,on);digitalWrite(LED_4,on);return;} if(c=='F'||c=='B'){uint8_t step=(now/120)%4;uint8_t p[4]={LED_1,LED_2,LED_3,LED_4}; if(c=='B')step=3-step; for(uint8_t i=0;i<4;i++)digitalWrite(p[i],i==step);} else {digitalWrite(LED_1,LOW);digitalWrite(LED_4,LOW);digitalWrite(LED_2,fabs(a)<2);digitalWrite(LED_3,fabs(a)<2);} }
