#include <SoftwareSerial.h>
#include <LowPower.h>

String DEVICE_NAME = "basement";

SoftwareSerial HC12(A2, A3);

#include <OneWire.h>
#include <DallasTemperature.h>
#define ONE_WIRE_BUS 9 
OneWire oneWire(ONE_WIRE_BUS); 
DallasTemperature sensors(&oneWire);

#include <DHT.h>
#define DHTPIN 3
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);



void setup() {
  pinMode(10, OUTPUT);
  digitalWrite(10, HIGH);

  pinMode(2, OUTPUT);
  pinMode(4, OUTPUT);
  digitalWrite(2, HIGH);
  digitalWrite(4, LOW);

  pinMode(A1, OUTPUT);
  digitalWrite(A1, HIGH);
  delay(1000);
  
  HC12.begin(9600);
  sensors.begin();
  dht.begin();
  }

void loop() {
  sensors.requestTemperatures(); 
  float hum = dht.readHumidity();
  float dhtTemp = dht.readTemperature();
  float dsTemp = sensors.getTempFByIndex(0);
  float batt = readVcc();
  String pkt;
  pkt = DEVICE_NAME + "|" + String(hum) + "|" + String(dhtTemp) + "|" + String(dsTemp) + "|" + String(batt) + "&";
  HC12.print(pkt);
  delay(100);

  // hc12 to sleep
  digitalWrite(A1, LOW);
  delay(100);
  HC12.print("AT+SLEEP"); 
  delay(100);
  digitalWrite(A1, HIGH);

  // turn off ds
  pinMode(10, OUTPUT);
  digitalWrite(10, LOW);

  // 30 minutes between temprature transissions
  for (int i = 0; i < 225; i++) 
  {
    LowPower.powerDown(SLEEP_8S, ADC_OFF, BOD_OFF);
  }

  pinMode(10, OUTPUT);
  digitalWrite(10, HIGH);

  digitalWrite(A1, LOW);
  delay(100);
  digitalWrite(A1, HIGH);

  // give it a sec
  delay(500);
}

long readVcc() 
{
  long result;
  ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
  delay(2);
  ADCSRA |= _BV(ADSC);
  while (bit_is_set(ADCSRA,ADSC));
  result = ADCL;
  result |= ADCH<<8;
  result = 1125300L / result;
  return result;
}
