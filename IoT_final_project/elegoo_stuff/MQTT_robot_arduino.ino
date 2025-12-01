// follow movement commands received from another device over UART, and when requested, turn the ultrasonic sensor to the desired angle and send back a distance reading over UART.

#include <Servo.h>
Servo servo; // create an object of the Servo class named "servo" (very original I know)

//pin definitions
#define echo 12
#define trig 13

#define stby 3 // needs to be HIGH for the motor driver to be on
#define pwmA 5 // channel A is the right motors
#define inA 7
#define pwmB 6 // channel B is the left motors
#define inB 8

// constants
const int motorSpeed = 128;

enum commands {
  STOP, FORWARD, BACKWARD, LEFT, RIGHT, READ_FORWARD, READ_LEFT, READ_RIGHT
};

//timestamp variables for timed actions
long ultrasonicT = 0;
long commandT = 0;

long servoReachAngleT = 0; // this timestamp is set in the future, the time at which the servo will have completed its swing. Based on the current angle, the target angle, and the approximate angular speed of the servo.

// variable values
byte distance = 0; // in cm.



// functions
int see() { // send out a pulse of ultrasound, wait for the pulse to echo back, and return its distance measurement.
  unsigned long duration; // in microseconds
  int dist; // in cm
  
  digitalWrite(trig, LOW); // returns the trig pin LOW for redundancy
  delayMicroseconds(2);
  
  digitalWrite(trig, HIGH); // Sets the trigPin to HIGH state for 10 micro seconds, which emits a short ultrasonic pulse
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  
  duration = pulseIn(echo, HIGH); // waits for the echo pin to go from LOW to HIGH, returns the time waited time in microseconds
  if (duration == 0) { // the pulseIn function will return 0 if it never gets back a pulse, which can happen if the sensor is too far away from am obstacle. To avoid this, we will change the value of the duration if we get a 0.
    duration = 15000; // force the duration to be a value that yields 255 cm of distance. This will make the robot consider a pulse duration of 0 to mean no obstacle ahead.
  }
  
  // Calculating the distance in cm. Because sound travels as a constant speed through air, we can find the linear relationship between sound travel duration and the distance that the sound travelled. Assuming air temperature stays around 25C.
  dist = (duration/2) * 0.034; // we divide by 2 because the sound also has to return back to the sensor, but we only care about the duration from the sensor to the obstacle.

  if (dist < 0){dist = 0;} if (dist > 255){dist = 255;} // clamp the distance between 0 and 255 to fit within a byte for easy transmission. Also, because it should never be negative and above 2.5-3m the sensor becomes unreliable.
  return dist;
}

void move(int pwmBval, int pwmAval) { // control the robot's tank drive. Function takes arguments in this order: pwmB (left motor) from -255 to +255, pwmA (right motor) from -255 to +255.
  
  analogWrite(pwmB, abs(pwmBval)*0.95);
  if (pwmBval < 0) {digitalWrite(inB, 0);} // the direction of the each side is controlled by the sign on the corresponding pwm value. If it is negative, go backwards, otherwise go forwards.
  else {digitalWrite(inB, 1);} // left motors direction
  
  analogWrite(pwmA, abs(pwmAval)*0.90); // slight reduction in the motor speeds in order to correct curved motion of the robot
  if (pwmAval < 0) {digitalWrite(inA, 0);} 
  else {digitalWrite(inA, 1);} // right motors direction
  
}



// body
void setup() {
  pinMode(trig, OUTPUT);

  pinMode(stby, OUTPUT);
  pinMode(pwmA, OUTPUT);
  pinMode(inA, OUTPUT);
  pinMode(pwmB, OUTPUT);
  pinMode(inB, OUTPUT);

  Serial.begin(115200);

  digitalWrite(stby, 1);

  servo.write(80); // servo is a bit off from center. Higher angles are left, lower angles are right.
  //servo.attach(10);

}



void loop() {
  long currentT = millis();

  if ( (currentT - ultrasonicT) >= 25 ) { // use ultrasonic sensor 40 times /s. Above around 50/s causes the code to glitch out.
    ultrasonicT = currentT;

    distance = see(); // change this to only happen when read commands are received
    Serial.write(distance);
    //Serial.println(distance);
  }

  if (Serial.available()) { // initiate robot actions based on which command was received through Serial
    byte command = Serial.read();
    commandT = millis();
    
    switch (command) {
      case STOP:
        move(0, 0);
        break;
      case FORWARD:
        move(motorSpeed, motorSpeed);
        break;
      case BACKWARD:
        move(-motorSpeed, -motorSpeed);
        break;
      case LEFT:
        move(-motorSpeed, motorSpeed);
        break;
      case RIGHT:
        move(motorSpeed, -motorSpeed);
        break;
      /*case READ_FORWARD: // wait before pinging the servo based on roughly how long it takes to get from the servo's current position to the desired one
        a
        break;
      case READ_LEFT:
        a
        break;
      case READ_RIGHT:
        a
        break;*/
    }
    
  }
  else if (currentT - commandT > 100) {move(0, 0);} // stop the robot if the serial connection to the ESP is interrupted
  
  
}
