#include "Adafruit_CCS811.h"

Adafruit_CCS811 ccs;

#define PIN_NOT_WAKE 5
#define PIN_NOT_INT 6

void setup() {
  Serial.begin(9600);

  Serial.println("CCS811 test");

  //Configure the wake line, start asleep
  pinMode(PIN_NOT_WAKE, OUTPUT);
  digitalWrite(PIN_NOT_WAKE, 0);
  if(!ccs.begin()){
    Serial.println("Failed to start sensor! Please check your wiring.");
    while(1);
  }

  ccs.setDriveMode(3);

  pinMode(PIN_NOT_INT, INPUT_PULLUP);
  ccs.enableInterrupt();
}

void loop() {
  if (digitalRead(PIN_NOT_INT) == 0) {
    Serial.println(ccs.checkError());
    ccs.readData();
    //Wake up the CCS811 logic engine
    digitalWrite(PIN_NOT_WAKE, 0);
    //Need to wait at least 50 us
    delay(100);

    if(ccs.available()){
      if(!ccs.readData()){
        Serial.print("CO2: ");
        Serial.print(ccs.geteCO2());
        Serial.print("ppm, TVOC: ");
        Serial.println(ccs.getTVOC());
      }
      else{
        Serial.println("ERROR!");
        while(1);
      }
      //Now put the CCS811's logic engine to sleep
      digitalWrite(PIN_NOT_WAKE, 1);
      //Need to be asleep for at least 20 us
      delay(100);
    }
  } else {
    Serial.println(PIN_NOT_INT);
  }

  delay(1000);
}

//TRY A NEW LIBRARY - SOMETHING IS WRONG WITH I2C ERROR CODE 0 SEE file:///C:/Users/Doug/Downloads/CCS811_datasheet-1.pdf
