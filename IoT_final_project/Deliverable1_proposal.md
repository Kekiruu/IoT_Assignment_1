
**Project Proposal**



We will control an Elegoo robot car using a Raspberry Pi as the brain, which remotely communicates to the ESP32 on the robot via MQTT. Both the Pi and the ESP are connected to one wifi network, and the ESP sends sensor data from the robot’s sensor to the Pi, which then makes a decision on where the robot should move and sends this back to the ESP. The Raspberry Pi will also host a webserver from which human operators can monitor the sensor values that the ESP is sending and manually command the robot if they choose. 
