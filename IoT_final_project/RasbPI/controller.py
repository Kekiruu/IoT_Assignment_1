import paho.mqtt.client as mqtt
import json
import time
import logging
import os
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from datetime import datetime

# Configuration
RULES_FILE = "/opt/iot_system/rules.json"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

#Global Variable
inAutoMode = 0 # only publish messages for obstacle avoidance if we are in auto mode (1) and not manual mode (0)
moveInstruction = "move forward"
ultraInstruction = "read forward"
distanceLeft = -1
distanceRight = -1
distanceForward = 255


# Monitoring files
PID_FILE = "/var/lib/iot_system/controller.pid"
HEARTBEAT_FILE = "/var/lib/iot_system/controller.heartbeat"
HISTORIAN_HEARTBEAT = "/var/lib/iot_system/historian.heartbeat"

logging.basicConfig(
    filename='iot_controller.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

# functions to hold the code for automatic movement logic

    

class IoT_Controller: 
    client = None
    rules = []
    mqtt_data = {}
    message_log = []
    
    
   
        
    def configure():
        

        filename = "rules.json"
        with open(filename,'r') as file:
            IoT_Controller.rules = json.load(file)
        #print (IoT_Controller.rules)

        IoT_Controller.client = mqtt.Client()
        IoT_Controller.client.on_message = IoT_Controller.on_message
        IoT_Controller.client.connect("localhost",1883)
        IoT_Controller.client.subscribe("#")
        
        '''broker_host = "mqtt.example.com"
        broker_port = 8883  # Secure MQTT
        IoT_Controller.client.connect(broker_host, broker_port)
        '''
    
    
    def on_message(client, userdata, message):
        global inAutoMode
        global moveInstruction
        global ultraInstruction
        global distanceLeft
        global distanceRight
        global distanceForward
        print("on_message happened")
        
        try: # this statement just executes an alternate block if there is some kind of error in the primary block, like trying to convert a string into a float
            value = float(message.payload.decode("utf-8"))
        except ValueError: #also known as error handling
            
            print("String")
            value = message.payload.decode("utf-8")
        topic = message.topic
        
        for entry in IoT_Controller.message_log:
            
            """if entry["time"] < time.time() - 5:
                IoT_Controller.message_log.remove(entry)
                print("remove happned")
            elif entry["topic"] == topic and entry["value"] == value:
                return"""
            
            if entry["topic"] == topic and entry["value"] == value: #comment this out after
                return

        if len(IoT_Controller.message_log) > 1:
            IoT_Controller.message_log.pop(0) # deletes the first index i the dictionary
        
        
        IoT_Controller.mqtt_data[topic] = value
        logging.info(f"Received: {topic} = {value}") #the first instance of logging info for what the user published
        print(topic, value)
        
        #initialize obstacle avoidance mode values
        if topic == "robot/instruction-request" and value == "begin obstacle avoidance" and not inAutoMode:
            inAutoMode = 1
            distanceAhead = 255
            distanceLeft = -1
            distanceRight = -1
            moveInstruction = "move forward"
            ultraInstruction = "read forward"
        #
        elif topic == "robot/manual-movement" and value == "stop":
            inAutoMode = 0
        
        #respond to the ESP asking for instructions or sending sensor data by publishing the relevant instructions
        if topic == "robot/telemetry/distance-ahead" and moveInstruction == "move forward":
            distanceForward = value
            if value >= 45:
                moveInstruction = "move forward"
                ultraInstuction = "read forward"
                distanceLeft = -1
                distanceRight = -1
                
            else:
                moveInstruction = "stop"
                ultraInstruction = "read left"
                print("left distance:")
                
        elif topic == "robot/telemetry/distance-ahead" and ultraInstruction == "read left" and distanceLeft == -1 :
            distanceLeft = value
            print(distanceLeft)
            ultraInstruction = "read right"
            print("right distance:")
        elif topic == "robot/telemetry/distance-ahead" and ultraInstruction == "read right" and distanceRight == -1 :
            distanceRight = value
            ultraInstruction = "compare"
            print(distanceRight)
            
        #this part decides which direction to turn based on the distance values acquired. It runs on the same program scan that the right distance is received.
        if topic == "robot/telemetry/distance-ahead" and distanceLeft > -1 and distanceRight > -1 and moveInstruction == "stop":
            print("comparing")
            #print(distanceForward)
            if distanceForward > distanceLeft and distanceForward > distanceRight:
                moveInstruction = "u-turn"
                
            
            elif distanceLeft > distanceRight:
                moveInstruction = "move left"
            else: #if distanceLeft < distanceRight:
                moveInstruction = "move right"
        
        elif topic == "robot/telemetry/distance-ahead" and (moveInstruction == "move left" or moveInstruction == "move right" or moveInstruction == "u-turn" ):
            print("laststep")
            if value >= 45:
                moveInstruction = "move forward"
                ultraInstruction = "read forward"
                
            
        
        
        if inAutoMode and topic != "robot/behaviour/drive" and topic != "robot/behaviour/ultrasonic-sensor": #any publication outide these 2 topics will cause the obstacle avoidance logic to execute and publish
            IoT_Controller.client.publish("robot/behaviour/drive", moveInstruction)
            IoT_Controller.client.publish("robot/behaviour/ultrasonic-sensor", ultraInstruction)
        
        #we dont need the rules anymore since the decision making is hard-coded. Th rules system was limiting due to only one action per rule and needing to spam MQTT to transmit many variables.
        """for rule in IoT_Controller.rules: # the rules itself is a dictionary, where every rule has some values (in this case an array of conditions (each of which is its own dictionary of values) & a dictionary of action values)
            conditions = rule["conditions"] # array of condition dictionaries, each of which contains the values for the given condition
            conditions_met = True
            #print(rule)
            
            for condition in conditions: # check each individual condition inside the conditions array
                topic = condition["topic"]
                #print(topic)
                try:
                    value = IoT_Controller.mqtt_data[topic]
                    condition_met = IoT_Controller.condition_met(
                        value,
                        condition["comparison"],
                        condition["value"]
                    )
                    #print (condition_met)
                except KeyError:
                    value = None
                    condition_met = False
                
                conditions_met = conditions_met and condition_met
                #print (conditions_met)
                #print (condition_met)
        
            if conditions_met:
                
                print("a condition was met")
                action = rule["action"]
                print(action["message"])
                #action["topic"]
                #action["value"]
                #logging.info(f"Received: {topic} = {value}")
                
                IoT_Controller.client.publish(action["topic"], action["value"])
                entry = {
                    "time": time.time(),
                    "topic": action["topic"],
                    "value": action["value"]
                }
                #print(topic)
                #print(value)
                logging.info("Received: {0[topic]} = {0[value]}".format(entry))
                IoT_Controller.message_log.append(entry)
                #print("append happend")
                
                #PUT THE LOGGING INFO HERE edit nevermind
        for entry in IoT_Controller.message_log:
            print(entry)
                
        

    def condition_met(value, comp_operator, comp_value): # from the "comparison" value in the conditions, converts the strings into actual if statement operators based on what that comparison value indicated. Then compute the comparison between the messaged value and the reference value.
        if comp_operator == ">":
            return value > comp_value
        if comp_operator == ">=":
            return value >= comp_value
        if comp_operator == "<":
            return value < comp_value
        if comp_operator == "<=":
            return value <= comp_value
        if comp_operator == "==":
            return value == comp_value
        if comp_operator == "!=":
            return value != comp_value"""
        
    def run():
        IoT_Controller.client.loop_start()
    
    

class ReloadHandler(BaseHTTPRequestHandler):
   
    
    def do_POST(self):
        
        if self.path == '/reload':
            print("Reload request received via HTTP")
            
            # Reload the rules
            e = IoT_Controller.load_rules()
            if e == None:
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'success', 'message': f'Loaded {len(IoT_Controller.rules)} rules'}
                self.wfile.write(json.dumps(response).encode())
                
                print(f"✓ Rules reloaded successfully ({len(IoT_Controller.rules)} rules)")
            else:
                # Send error response
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode())
                
                print(f"✗ Error reloading rules: {e}")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        
        pass
    
        
        
def run_http_server():
    
    server = HTTPServer(('localhost', 5001), ReloadHandler)
    print("HTTP reload endpoint: http://localhost:5001/reload")
    server.serve_forever()
   
def signal_handler(signum, frame):
    """Handle shutdown and reload signals"""
    if signum == signal.SIGHUP:
        # SIGHUP = reload configuration
        print("\nReceived SIGHUP signal, reloading rules...")
        e = IoT_Controller.load_rules()
        if e == None:
            print(f"✓ Rules reloaded ({len(IoT_Controller.rules)} rules)")
        else:
            print(f"✗ Error reloading rules: {e}")
            
    elif signum == signal.SIGTERM or signum == signal.SIGINT:
        # SIGTERM/SIGINT = shutdown
        print(f"\nReceived signal {signum}, shutting down controller...")
        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)
        sys.exit(0)
        
def save_pid():
        """Save process ID"""
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        print(f"Controller PID {os.getpid()} saved to {PID_FILE}")

def update_heartbeat():
    """Update heartbeat timestamp"""
    with open(HEARTBEAT_FILE, 'w') as f:
        f.write(datetime.now().isoformat())

def check_historian_health():
    """Check if historian is running by reading its heartbeat"""
    try:
        with open(HISTORIAN_HEARTBEAT, 'r') as f:
            last_beat = f.read().strip()
            # Parse timestamp
            last_time = datetime.fromisoformat(last_beat)
            age_seconds = (datetime.now() - last_time).seconds
            
            if age_seconds < 15:
                print(f"✓ Historian is healthy (heartbeat {age_seconds}s ago)")
                return True
            else:
                print(f"⚠ WARNING: Historian heartbeat is {age_seconds}s old - may be dead!")
                return False
    except FileNotFoundError:
        print("✗ ERROR: Historian heartbeat file not found - Historian may not be running!")
        return False
    except Exception as e:
        print(f"✗ ERROR checking historian: {e}")
        return False
    


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGHUP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Save PID
    save_pid()
    
    # Check if historian is running
    check_historian_health()
    
    # Configure and start controller
    IoT_Controller.configure()
    IoT_Controller.run()  # Starts MQTT in background
    
    # Start HTTP reload server in background thread
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()
    
    print("IoT Controller started successfully")
    print(f"  - MQTT: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  - HTTP reload: http://localhost:5001/reload")
    print(f"  - Manual reload: kill -HUP {os.getpid()}")
    
    # Main loop with heartbeat
    try:
        while True:
            update_heartbeat()
            #publishMovement()
            
            time.sleep(5) # maybe lower this is the heartbeat function permits
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    finally:
        if os.path.exists(HEARTBEAT_FILE):
            os.remove(HEARTBEAT_FILE)
        print("IoT Controller shut down cleanly")    
    
        


