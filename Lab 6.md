what you have learned,

1.I learn how to install the mqtt library and how to use it.

what you found difficult to understand,

2.Not much everything was straight foward the only issue I really had was that I forgot to put my file in a VENV so I couldn't download paho-mqqt

what you found easy to understand and what you think may have made this easy for you,

3.almost everything,like the usual basically everything we need is written in github all I had to do was follow it. 

what you believe you need to improve,

4.Getting used to using VENV

what the teacher could have said or done to make learning easier,

5.not much, any issues I had were answered and the instruction are good

what you could have done to make the learning easier, and

6.same thing then lab 4-5, not jumping instruction and actually read them.

other reflections that you find relevant to your personal development.

7.None for this lab

////////////////////////////////////////
sudo usermod -a -G dialout <username> we uses this in the terminal to be able to connect ot it by mqtt

we also copied a micropython code into the esp32 so we could connect the esp32 device to a wifi network.:
import time
import network
#network is used to access the ESP32’s Wi-Fi interface in station mode, letting it join an existing network.

WIFI_SSID = "WiFi_SSID"
WIFI_PASS = "WiFi_password"

def wifi_connect():
    #Initializes the station interface with network.WLAN(network.STA_IF) and activates it.
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    #Initiates a connection with the credentials.
    sta.connect(WIFI_SSID, WIFI_PASS)
    #Pause the application until we know WiFi is connected
    while not sta.isconnected():
        print("connecting...")
        time.sleep(1)
    #Once connected, the network info is printed for reference
    print(f"WiFi connected {sta.ifconfig()}")
    return sta.isconnected()

def main():
    # Wi-Fi
    wifi_connect()

if __name__ == '__main__':
    main() 

The rest was mostly to know how to connect a I2C devices and acquiring its data/ How to subcribe and publish message with MQTT

Like whats the broker/topic/client





