// Program for an ESP mounted on the robot to talk to the arduino via UART. It publishes sensor data from the Arduino to MQTT, and sends movement commands to the arduino from MQTT.
// Original code for MQTT client written by Tony DiCola for Adafruit Industries.

#include <ESP8266WiFi.h>
#include "Adafruit_MQTT.h"
#include "Adafruit_MQTT_Client.h"

#define WLAN_SSID       "iot_wireless" // replace with wifi credentials
#define WLAN_PASS       "passphrase"

//Adafruit.io MQTT setup. The username and key are not needed unless you use the Adafruit IO website as a broker.
#define AIO_SERVER      "192.168.51.205" // replace with IP address of the broker. Also see Serial monitor for ESP's IP address and put that into the broker code.
#define AIO_SERVERPORT  1883                   // use port 8883 for SSL
#define AIO_USERNAME    ""
#define AIO_KEY         ""

// Create an ESP8266 WiFiClient class to connect to the MQTT server.
WiFiClient client;

// Setup the MQTT client class by passing in the WiFi client and MQTT server and login details.
Adafruit_MQTT_Client mqtt(&client, AIO_SERVER, AIO_SERVERPORT, AIO_USERNAME, AIO_KEY);

// Topics. If using Adafruit broker, use format: <username>/feeds/<feedname>

// topics to publish to
Adafruit_MQTT_Publish distanceReading = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "robot/telemetry/distance-ahead"); // one-way message from the robot to the Pi consisting of the distance in cm that the ultrasonic sensor is reading, from 0-255.
// Adafruit_MQTT_Publish floorReading = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "robot/telemetry/reflected-light-below"); // this probably aint gonna happen

// topics to subscribe to 
Adafruit_MQTT_Subscribe driveCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/behaviour/drive"); // one way message from the Pi to the robot to produce movement.
Adafruit_MQTT_Subscribe senseCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/behaviour/ultrasonic-sensor"); // every time the Pi publishes an ultrasonic read instruction, the robot will turn the sensor to that angle, get the distance, and then publish it back to the Pi as an acknowledgement.
Adafruit_MQTT_Subscribe manualMoveCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/manual-movement");
/// whenever the ESP sees that the sensor topic has been filled with an instruction, it first publishes a blank message back so that each instruction publication from the Pi only causes 1 sensor reading to happen. Then it updates the sensor value, which in turn gets read and then erased by the Pi.
/// edit: nvm, this is probably not needed since the subscriber is only notified once when a message is published, not continuously as long as the topic contains a message


// actual robot code begins
#define publishEnablePin 1

enum commandToRobot { // numerical values which will be written to the arduino via Serial, and then read accordingly by the receiver. Enumerated for human-readability in both the sender and receiver code.
  STOP, FORWARD, BACKWARD, LEFT, RIGHT, READ_FORWARD, READ_LEFT, READ_RIGHT // the last 3 are called by the Pi in obstacle avoidance to get the robot to return a distance reading in the desired direction
};

long lastPubT = 0; // timestamp for periodic publishing timer

int ultrasonicValue = 255; // distance in cm detected by the sensor



void MQTT_connect() { // Function to connect and reconnect as necessary to the MQTT server. Should be called in the loop function and it will take care of connecting.
  int8_t ret;

  // end the function here if already connected.
  if (mqtt.connected()) {
    return;
  }

  //Serial.print("Connecting to MQTT... ");

  uint8_t retries = 3;
  while ((ret = mqtt.connect()) != 0) { // connect will return 0 for connected
       //Serial.println(mqtt.connectErrorString(ret));
       //Serial.println("Retrying MQTT connection in 5 seconds...");
       mqtt.disconnect();
       delay(5000);  // wait 5 seconds
       retries--;
       if (retries == 0) {
         // basically die and wait for WDT to reset me
         while (1);
       }
  }
  //Serial.println("MQTT Connected!");
}



void setup() {

  pinMode(publishEnablePin, INPUT_PULLUP);

  Serial.begin(115200); // Do not Serial.print in the loop if the TX pin is connected to arduino, or it will receive unwanted bytres and may move unexpectedly. Printing once in setup is fine to get the IP address.
  delay(10);

  //Serial.println(F("Adafruit MQTT client for robot control"));

  // Connect to WiFi access point.
  //Serial.println(); Serial.println();
  //Serial.print("Connecting to ");
  //Serial.println(WLAN_SSID);

  WiFi.begin(WLAN_SSID, WLAN_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    //Serial.print(".");
  }
  //Serial.println();

  Serial.println("WiFi connected");
  Serial.println("IP address: "); Serial.println(WiFi.localIP());
  delay(250);
  
  // Setup MQTT subscription
  mqtt.subscribe(&driveCommand);
  mqtt.subscribe(&senseCommand);
  mqtt.subscribe(&manualMoveCommand);
  
}



void loop() {
  // Ensure the connection to the MQTT server is alive (this will make the first
  // connection and automatically reconnect when disconnected).  See the MQTT_connect
  // function definition further below.
  MQTT_connect();

  long currentT = millis();

  // this is our 'wait for incoming subscription packets' busy subloop
  // try to spend your time here

  Adafruit_MQTT_Subscribe *subscription;
  while ((subscription = mqtt.readSubscription(10))) { // reduce time to read this really fast and reduce code blocking. if needed, use a timer to slow down publications.
    if (subscription == &driveCommand) {
      //Serial.print(F("Got drive command: "));
      //Serial.println((char *)driveCommand.lastread);

      if ((char *)driveCommand.lastread == "stop") {Serial.write(STOP);} // relay the mqtt messages as Serial transmissions to the arduino
      if ((char *)driveCommand.lastread == "forward") {Serial.write(FORWARD);}
      if ((char *)driveCommand.lastread == "backward") {Serial.write(BACKWARD);}
      if ((char *)driveCommand.lastread == "left") {Serial.write(LEFT);}
      if ((char *)driveCommand.lastread == "right") {Serial.write(RIGHT);}
      
    }
    if (subscription == &senseCommand) {
      //Serial.print(F("Got sense command: "));
      //Serial.println((char *)senseCommand.lastread);

      if ((char *)senseCommand.lastread == "read forward") {Serial.write(READ_FORWARD);}
      if ((char *)senseCommand.lastread == "read left") {Serial.write(READ_LEFT);}
      if ((char *)senseCommand.lastread == "read right") {Serial.write(READ_RIGHT);}
    }
    if (subscription == &manualMoveCommand) {
      //Serial.print(F("Got manual move command: "));
      //Serial.println((char *)manualMoveCommand.lastread);

      if ((char *)manualMoveCommand.lastread == "stop") {Serial.write(STOP);}
      if ((char *)manualMoveCommand.lastread == "forward") {Serial.write(FORWARD);}
      if ((char *)manualMoveCommand.lastread == "backward") {Serial.write(BACKWARD);}
      if ((char *)manualMoveCommand.lastread == "left") {Serial.write(LEFT);}
      if ((char *)manualMoveCommand.lastread == "right") {Serial.write(RIGHT);}
    }
    //if else 
  }

  //update distance from UART value
  if (Serial.available()) {
    int byteReceived = (Serial.read());
    ultrasonicValue = byteReceived; // for now dont need to manipulate the value or make decisions based upon it
  }
  // periodically publish distance readings
  if (currentT - lastPubT > 100) { 
    lastPubT = currentT;
    // Now we can publish stuff!
    if (1) { // dont publsh if the enable pin is pulled low
      //Serial.print(F("\nSending distanceReading val "));
      //Serial.print(ultrasonicValue);
      //Serial.print("...");

      if (! distanceReading.publish(ultrasonicValue)) { // the actual publication function to the given topic object
        //Serial.println(F(" Failed to send"));
      } else {
        //Serial.println(F(" Sent"));
      }
    }

  }
  // ping the server to keep the mqtt connection alive
  // NOT required if you are publishing once every KEEPALIVE seconds
  /*
  if(! mqtt.ping()) {
    mqtt.disconnect();
  }
  */
}
