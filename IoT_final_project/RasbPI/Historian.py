import paho.mqtt.client as mqtt
import sqlite3
import os
import signal
import sys
import time
from datetime import datetime

# PID and heartbeat files for monitoring
PID_FILE = "/tmp/historian.pid"
HEARTBEAT_FILE = "/tmp/historian.heartbeat"

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "#"
MQTT_CLIENT_ID = "historian-client"
DB_FILE = "historian_data.db"

def save_pid():
    """Save process ID to file for monitoring"""
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    print(f"Historian PID {os.getpid()} saved to {PID_FILE}")

def update_heartbeat():
    """Update heartbeat file with current timestamp"""
    with open(HEARTBEAT_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nReceived signal {signum}, shutting down historian...")
    # Clean up heartbeat file
    if os.path.exists(HEARTBEAT_FILE):
        os.remove(HEARTBEAT_FILE)
    sys.exit(0)
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT")
    client.subscribe(MQTT_TOPIC)
    
    
def on_message(client, userdata, msg):
    print("Got a message")
    payload = msg.payload.decode()  # Convert bytes to string
    topic = msg.topic
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_to_database(topic, payload, timestamp)
    
    
def save_to_database(topic, payload, timestamp):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    SQL = "CREATE TABLE IF NOT EXISTS historian_data (topic TEXT, message TEXT, timestamp TEXT);"
    cursor.execute(SQL)

    SQL = "INSERT INTO historian_data (topic, message, timestamp) VALUES (?,?,?);"
    cursor.execute(SQL, (topic, payload, timestamp))

    conn.commit()  # Commit ensures data is saved
    conn.close()
    
if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Save PID for monitoring
    save_pid()
    
    # Create MQTT client
    client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect and start
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"Historian connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.loop_start()  # Start in background thread
        
        # Main loop - update heartbeat every 5 seconds
        while True:
            update_heartbeat()
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)
        print("Historian shut down cleanly.")


try:
    while True:
        pass
except KeyboardInterrupt:
    client.disconnect()

