#**which applications will handle which tasks**

Raspberry Pi: It will host the MQTT broker for two-way communication with the ESP32. The Pi is subscribed to the topics that the ESP32 publishes its sensor data to, and the Pi will perform all decision-making needed to move the Robot car around the floor and avoid obstacles and send those decisions back to the ESP. Also, the Pi will handle the web server to display sensor data from the robot and obtain inputs from human operators to manually control the robot.

ESP32: It is subscribed to the topics that the Pi publishes its movement instructions to. Based on these instructions, the ESP will output signals to control the motor drivers on the Elegoo robot car and move around on the floor. As it moves, it reads data from its sensors including an ultrasonic sensor, and sends this data back to the Pi for processing.

MQTT: This serves as the communication path between the Raspberry Pi and the ESP32. There will be topics for each of the values that are being sent back and forth between the Pi and ESP. For example, the ultrasonic sensor will be a topic with the value in centimeters, which is published by the ESP. Also, the movement direction will be a topic with a string value such as “forward” or “right” being published by the Raspberry Pi. 

HTTP Web server: displays in real-time the data that are being published on the MQTT topics for users to see. Also allows the user to toggle between automatic movement and manual movement mode if they wish to manually control the robot using the web server’s GUI. 

#**which conditions will lead to which results**

On the webserver there will be a mode selector and general control to move the car. The 2 modes will be obstacle avoidance and manual. 

For obstacle avoidance the car will continue to move forward until the car's ultrasonic sensor detects something in front of it. It will stop and scan left and right to see where it could move

For the manual mode it will just follow in input given on the web server. The movement would be forward,backward, left and right.


#**which devices will be used**

Elegoo Robot car
Sensors:
-Ultrasonic

-Maybe infrared (IR) sensor for line following

Actuator:
-4 Motors
-1 Servo

