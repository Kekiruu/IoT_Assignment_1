// Program for an ESP mounted on the robot to talk to the arduino via UART. It publishes sensor data from the Arduino to MQTT, and sends movement commands to the arduino from MQTT.
// Original code for MQTT client written by Tony DiCola for Adafruit Industries.

#include <ESP8266WiFi.h>
#include "Adafruit_MQTT.h"
#include "Adafruit_MQTT_Client.h"

#define WLAN_SSID       "iot_wireless" // replace with wifi credentials
#define WLAN_PASS       "passphrase"

//Adafruit.io MQTT setup. The username and key are not needed unless you use the Adafruit IO website as a broker.
#define AIO_SERVER      "192.168.51.205" // replace with IP address of the broker, which depends on the network ID (ifconfig on the broker). Also see Serial monitor for ESP's IP address, if needed.
#define AIO_SERVERPORT   1883                   // use port 8883 for SSL
#define AIO_USERNAME    ""
#define AIO_KEY         ""

// Create an ESP8266 WiFiClient class to connect to the MQTT server.
WiFiClient client;

// Setup the MQTT client class by passing in the WiFi client and MQTT server and login details.
Adafruit_MQTT_Client mqtt(&client, AIO_SERVER, AIO_SERVERPORT, AIO_USERNAME, AIO_KEY);

// Topics. If using Adafruit broker, use format: <username>/feeds/<feedname>

// topics to publish to
Adafruit_MQTT_Publish distanceReading = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "robot/telemetry/distance-ahead"); // one-way message from the robot to the Pi consisting of the distance in cm that the ultrasonic sensor is reading, from 0-255.
Adafruit_MQTT_Publish instructionRequest = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "robot/instruction-request"); // if not periodically publishing an ultrasonic distance, then you may need to publish a default message in order to trigger the onMessage function in the Pi and force it to continue the obstacle avoidance algorithm

// topics to subscribe to 
Adafruit_MQTT_Subscribe driveCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/behaviour/drive"); // one way message from the Pi to the robot to produce movement.
//Adafruit_MQTT_Subscribe stateCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/behaviour/state"); // 
Adafruit_MQTT_Subscribe ultrasonicCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/behaviour/ultrasonic-sensor"); // every time the Pi publishes an ultrasonic read instruction, the robot will turn the sensor to that angle, get the distance, and then publish it back to the Pi as an acknowledgement.
Adafruit_MQTT_Subscribe manualMoveCommand = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "robot/manual-movement"); // keep manual drive instructions seperate from auto ones to distinguish a "stop" movmement from the Pi from a "stop" command from the user to end auto mode.
//Adafruit_MQTT_Subscribe instructionRequest = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "robot/instruction-request"); // also subscribe to this topic to be notified of when the robot enters automatic movement mode


// actual robot code begins
#define publishEnablePin 1

const int turnDuration = 250; // approximate time to turn left/right in ms. Perhaps make these writeable from Pi publications.
const int uturnDuration = 800;

enum commandToRobot { // numerical values which will be written to the arduino via Serial, and then read accordingly by the receiver. Enumerated for human-readability in both the sender and receiver code.
  STOP, FORWARD, BACKWARD, LEFT, RIGHT, READ_FORWARD, READ_LEFT, READ_RIGHT // the last 3 are called by the Pi in obstacle avoidance to get the robot to return a distance reading in the desired direction
};

long lastPubT = 0; // timestamp for periodic publishing timer. If this grows over 100ms and the ESP has nothing to say to the Pi, just send a default message to trigger the Pi's on message funnction 
long successfulPingT = 0; // timestamp for when the broker was last successfully pinged
long lastWriteT = 0; // timestamp to limit Serial write rate to avoid filling up the Arduino's Serial buffer. 
long turnWillFinishT = 0; // time in the future at which the choreographed turn in automatic mode will finish

int ultrasonicValue = 255; // distance in cm detected by the sensor, which will be updated by the arduino over Serial as soon as the robot's servo stops turning the sensor

byte lastMovementCmd = 0; // the byte that will be sent over serial. Preserve the last received instruction in between publications from the Pi so that the arduino can constantly be signaled.

bool askingForDistance = 0; // goes true when a new ultasonic instruction from the Pi first comes in, goes false after the ESP publishes the distance for the Pi to see.
bool receivedNewDistance = 0; // goes false when a new ultrasonic instruction from the Pi first comes in, goes true after the arduino answers with a distance for the ESP to publish.
bool performingTimedTurn = 0; // for starting and stopping timed turns in obstacle mode

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

void timeAutomaticTurns(long now, String cmmd) { // set up the a turn motion for a certain period of time when turning in osbstacle avoidance, because the python Controller code does not handle timed events.
  if (cmmd == "move left") {
    lastMovementCmd = LEFT;
    turnWillFinishT = now + turnDuration;
    performingTimedTurn = 1;
  }
  if (cmmd == "move right") {
    lastMovementCmd = RIGHT;
    turnWillFinishT = now + turnDuration;
    performingTimedTurn = 1;
  }
  if (cmmd == "u-turn") {
    lastMovementCmd = RIGHT;
    turnWillFinishT = now + uturnDuration;
    performingTimedTurn = 1;
  }
}



void setup() {

  pinMode(publishEnablePin, INPUT_PULLUP);

  Serial.begin(115200); // Do not Serial.print in the loop if the TX pin is connected to arduino, or it will receive unwanted bytes and may move unexpectedly. Printing once in setup is fine to get the IP address.
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

  Serial.print("WiFi connected: "); Serial.println(WLAN_SSID);
  Serial.println("My IP address: "); Serial.println(WiFi.localIP());
  delay(250);
  
  // Setup MQTT subscription
  mqtt.subscribe(&driveCommand);
  mqtt.subscribe(&ultrasonicCommand);
  mqtt.subscribe(&manualMoveCommand);
  //mqtt.subscribe(&instructionRequest);
  
}



void loop() {
  // Ensure the connection to the MQTT server is alive (this will make the first
  // connection and automatically reconnect when disconnected).  See the MQTT_connect
  // function definition further below.
  MQTT_connect();

  long currentT = millis();

  // check if there is one or more publications to read from any of the topics that the ESP is subscribed to. If so, then make decisions based on which topic and what message is containted.
  Adafruit_MQTT_Subscribe *subscription;
  while ((subscription = mqtt.readSubscription(10))) { // reduce time to read this really fast and reduce code blocking. if needed, use a timer to slow down publications.
    // automatic movement topic
    if (subscription == &driveCommand) {
      String cmd = (char *)driveCommand.lastread; // store the commands in a short-named variable and convert it to a string for conventient if statements
      //Serial.print(F("Got drive command: "));
      //Serial.println(cmd);

      if (cmd == "stop")          {lastMovementCmd = STOP;} // relay the mqtt messages as Serial transmissions to the arduino
      if (cmd == "move forward")  {lastMovementCmd = FORWARD;}
      if (cmd == "move backward") {lastMovementCmd = BACKWARD;}
      timeAutomaticTurns(currentT, cmd); // set up timestamp for how long the robot should turn before stopping
      
    }
    // automatic sensor scanning topic
    if (subscription == &ultrasonicCommand) {
      String cmd = (char *)ultrasonicCommand.lastread;
      askingForDistance = 1; //   let the code know that an ultrasonic distance reading has been requested
      receivedNewDistance = 0; // and let the code know that the arduino has not yet replied with a distance reading
      //Serial.print(F("Got sense command: "));
      //Serial.println(cmd);

      if (cmd == "read forward") {Serial.write(READ_FORWARD);}
      if (cmd == "read left")    {Serial.write(READ_LEFT);}
      if (cmd == "read right")   {Serial.write(READ_RIGHT);}
    }
    // manual movement topic
    if (subscription == &manualMoveCommand) {
      String cmd = (char *)manualMoveCommand.lastread; 
      //Serial.print(F("Got manual move command: "));
      //Serial.println(cmd);

      if (cmd == "stop") {
        lastMovementCmd = STOP;
        askingForDistance = 0; // reset the variables associated with automatic movement
        receivedNewDistance = 0;
        ultrasonicValue = 255;
      }
      if (cmd == "forward")  {lastMovementCmd = FORWARD;}
      if (cmd == "backward") {lastMovementCmd = BACKWARD;}
      if (cmd == "left")     {lastMovementCmd = LEFT;}
      if (cmd == "right")    {lastMovementCmd = RIGHT;}
    }
    
  }
 // after the duration of the timed turn motion has elapsed, stop the robot and tell the arduino to return another distance reading to trigger the on_message function in the Pi again to continue obstacle avoidance algorithm
  if (currentT >= turnWillFinishT && performingTimedTurn) {
    Serial.write(READ_FORWARD); // the arduino takes some time to turn the servo back to forward, so it will only return a distance some time after the robot has stopped even if the stop command is Serial written at the same time.
    lastMovementCmd = STOP;
    performingTimedTurn = 0;
  }

  // decide whether to send last received movement instruction to the arduino based on connection strength with the broker, to avoid a runaway robot.
  if (mqtt.ping()) {
    successfulPingT = currentT;
  }
  if (currentT - lastWriteT >= 20) { // 20ms is probably way over the amount of time it normally takes for the arduino to read a single message in its Serial buffer, but hey, better to be safe than sorry.
    lastWriteT = currentT;

    if (currentT - successfulPingT >= 500) { // stop the robot if the mqtt connection is lost / too unstable
      Serial.write(STOP);
    }
    else {
      Serial.write(lastMovementCmd); // in normal conditions, send the last received movement command
    }
    
  }

  //update ultrasonic distance from UART value every time it's available
  if (Serial.available()) {
    
    int byteReceived = (Serial.read());
    ultrasonicValue = byteReceived; // we dont need to manipulate the value or make decisions based upon it. It's already assured that the value is an ultrasonic reading, and can only be from 0 to 255.
    receivedNewDistance = 1;
  }

  // publish the newly received ultrasonic value after it is requested by the Pi and measured by the arduino. This will only happen once for every time the Pi requests a distance value.
  if ( askingForDistance && receivedNewDistance && (currentT - lastPubT >= 100) ) { // wait 100ms before publishing the next ultasonic reading to avoid spamming the broker with too many historian write updates.
    lastPubT = currentT;
    askingForDistance = 0;
    distanceReading.publish(ultrasonicValue);
    /*else {
      lastPubT = currentT;
      instructionRequest.publish("on_message trigger")
    }*/
  }



}