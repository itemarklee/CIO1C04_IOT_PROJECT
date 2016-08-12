"""
g49pi(Mark) - For Goup Project  
"""

#!/usr/bin/env python3

# Send beacons detected periodically to AWS IoT.  Based on bluez library.
# Must be run with "sudo python3"

import time
import datetime
import ssl
import json
import paho.mqtt.client as mqtt
import bluetooth.ble as ble
# For grovepi
import grovepi
#Grove I2C color LCD
from grove_rgb_lcd import *


# TODO: Change this to the name of our Raspberry Pi, also known as our "Thing Name"
deviceName = "g49pi"

# Public certificate of our Raspberry Pi, as provided by AWS IoT.
deviceCertificate = "tp-iot-certificate.pem.crt"
# Private key of our Raspberry Pi, as provided by AWS IoT.
devicePrivateKey = "tp-iot-private.pem.key"
# Root certificate to authenticate AWS IoT when we connect to their server.
awsCert = "aws-iot-rootCA.crt"
isConnected = False

#GrovePi Connections
# Grove LED to digital port D4 - Debug
led = 4
# Grove Flame Sensor to port D2
flame = 2
# Connect the Grove Relay to digital port D3
# SIG,NC,VCC,GND
relay = 3

# This is the main logic of the program.  We connect to AWS IoT via MQTT, send sensor data periodically to AWS IoT,
# and handle any actuation commands received from AWS IoT.
def main():
    global isConnected
    # Create an MQTT client for connecting to AWS IoT via MQTT.
    client = mqtt.Client(deviceName + "_sr")  # Client ID must be unique because AWS will disconnect any duplicates.
    client.on_connect = on_connect  # When connected, call on_connect.
    client.on_message = on_message  # When message received, call on_message.
    client.on_log = on_log  # When logging debug messages, call on_log.

    # Set the certificates and private key for connecting to AWS IoT.  TLS 1.2 is mandatory for AWS IoT and is supported
    # only in Python 3.4 and later, compiled with OpenSSL 1.0.1 and later.
    client.tls_set(awsCert, deviceCertificate, devicePrivateKey, ssl.CERT_REQUIRED, ssl.PROTOCOL_TLSv1_2)

    # Connect to AWS IoT server.  Use AWS command line "aws iot describe-endpoint" to get the address.
    print("Connecting to AWS IoT...")
    client.connect("A1P01IYM2DOZA0.iot.us-west-2.amazonaws.com", 8883, 60)

    # Start a background thread to process the MQTT network commands concurrently, including auto-reconnection.
    client.loop_start()

    # Create the beacon service for scanning beacons.
    beacon_service = ble.BeaconService()

    # Configure the Grove LED, Flame, Relay port for output.
    grovepi.pinMode(led, "OUTPUT")
    grovepi.pinMode(relay,"OUTPUT")
    grovepi.pinMode(flame, "INPUT")
    #Supply Power to relay. Door Lock ON
    #grovepi.digitalWrite(led, 1)
    time.sleep(1)

    #FireMessage
    fireMesssage = "no"
    #To track students in area
    studentIDsInArea = ""
    #Location
    location = "Lab88"
    
    # Loop forever.
    while True:
        try:
            """
            #Test flame sensor using LED
            print (grovepi.digitalRead(flame))
            if (isFireDected()):
                grovepi.digitalWrite(led, 1)
            else:
                grovepi.digitalWrite(led, 0)
            """
            #Check for Fire in location
            fireMesssage = isFireDected()
                        
            # If we are not connected yet to AWS IoT, wait 1 second and try again.
            if not isConnected:
                time.sleep(1)
                continue

            # Scan for beacons and add to the sensor data payload.
            beaconsDict = {} #For Payload
            beaconsArray = []
            beacons_detected = beacon_service.scan(2)
            for beacon_address, beacon_info in list(beacons_detected.items()):
                # For each beacon found, add to the payload. Need to flip the bytes.
                beacon = {
                    "uuid": beacon_info[0].replace('-', ''),
                    "major": (beacon_info[1] % 256) * 256 + beacon_info[1] // 256,
                    "minor": (beacon_info[2] % 256) * 256 + beacon_info[2] // 256,
                    "power": beacon_info[3],
                    "rssi": beacon_info[4],
                    "address": beacon_address
                }
                uuid_temp =  beacon_info[0].replace('-', '')
                address_temp = beacon_address
                major_temp = (beacon_info[1] % 256) * 256 + beacon_info[1] // 256
                minor_temp = (beacon_info[2] % 256) * 256 + beacon_info[2] // 256
                #Add each beacon to the Dictionary
                beaconsArray.append(beacon)
                #StudentID will be configured as beacon MinorID for indentification
                studentIDsInArea = studentIDsInArea + str(minor_temp) + ","

            #Format String for output
            studentIDsInArea = studentIDsInArea[:-1]

            # Prepare our sensor data in JSON format.
            # Send reported state to g49pi
            payload = {
                "state": {
                    "reported": {
                        "beacons": beaconsArray,
                        "location": location,
                        "fire": fireMesssage,
                        "studentIDsInArea": studentIDsInArea,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                }
            }

            print("Sending sensor data to AWS IoT...\n" +
                  json.dumps(payload, indent=4, separators=(',', ': ')))

            # Publish our sensor data to AWS IoT via the MQTT topic, also known as updating our "Thing Shadow".
            client.publish("$aws/things/" + deviceName + "/shadow/update", json.dumps(payload))
            print("Sent to AWS IoT")

            #Reset studentIDsInArea
            studentIDsInArea = ""

            # Wait 15 seconds before sending the next set of sensor data. i.e. Beacons detected
            time.sleep(15)

        except KeyboardInterrupt:
            # Stop the program when we press Ctrl-C.
            grovepi.digitalWrite(relay,1)#lock door, resume power to relay 
            grovepi.digitalWrite(led, 1)#LED ON - Simulate Door LED
            break
        except Exception as e:
            # For all other errors, we wait a while and resume.
            print("Exception: " + str(e))
            time.sleep(10)
            continue

# Method to detected presence of Fire in location
def isFireDected():
    #GrovePi output 1 means no fire.
    if (grovepi.digitalRead(flame)):
        grovepi.digitalWrite(led, 0)
        return "no"
        #return False
    #Fire detected, set fire message
    else:
        grovepi.digitalWrite(led, 1)
        return "yes"
        #return True

# This is called when we are connected to AWS IoT via MQTT.
# We subscribe for notifications of desired state updates.
def on_connect(client, userdata, flags, rc):
    global isConnected
    isConnected = True
    print("Connected to AWS IoT")
    # Subscribe to our MQTT topic so that we will receive notifications of updates.
    topic = "$aws/things/" + deviceName + "/shadow/update/accepted"
    print("Subscribing to MQTT topic " + topic)
    client.subscribe(topic)
    #Lambda Function: g49_ActuateDoor will update G49Trace desired state.
    topicG49Trace = "$aws/things/g49Trace/shadow/update/accepted"
    print("Subscribing to MQTT topic " + topicG49Trace )
    client.subscribe(topicG49Trace)


# This is called when we receive a subscription notification from AWS IoT.
def on_message(client, userdata, msg):
   
    # Convert the JSON payload to a Python dictionary.
    # The payload is in binary format so we need to decode as UTF-8.
    payload2 = json.loads(msg.payload.decode("utf-8"))
    print("Received message, topic: " + msg.topic + ", payload:\n" +
          json.dumps(payload2, indent=4, separators=(',', ': ')))

    # If there is a desired state in this message, then we actuate,
    # e.g. if we see "lockStatus=unlock", we unlock the Door.
    if payload2.get("state") is not None and payload2["state"].get("desired") is not None:
        # Get the desired state and loop through all attributes inside.
        desired_state = payload2["state"]["desired"]
        for attribute in desired_state:
            if attribute == "doorLocation":
                doorlocation = desired_state.get(attribute)
                print("DOOR************"+doorlocation)
                print("No need to actutate this attribute")
                return # skip this attribute, for information only.
            if attribute == "lockStatus":
                # We handle the attribute and desired value by actuating.
                value = desired_state.get(attribute)
                #print("DOOR1************" + doorlocation)
                actuateDoor(client, attribute, value, "Lab88")  
            #Internal Fire, Unlocks All Doors, Send users in Lab to Command Center
            if attribute == "studentIDsInArea":
                # We handle the attribute and desired value by actuating.
                value = desired_state.get(attribute)
                internalFireActuateDoorNLCD(client, attribute, value, "Lab88")
            #External Fire, Unlocks All Lab Doors.
            if attribute == "fire":
                # We handle the attribute and desired value by actuating.
                value = desired_state.get(attribute)
                externalFireActuateDoorNLCD(client, attribute, value, "Lab88")

# Control my actuators based on the specified attribute and value,
# "fire=yes", we unlock the Door.
def externalFireActuateDoorNLCD(client, attribute, value, doorLocation):        
    #To track students in area
    studentIDsInArea1 = ""
    # Create the beacon service for scanning beacons.
    beacon_service1 = ble.BeaconService()
    #From Lambda Function: g49_ActuateDoor will update G49Trace desired state. 
    if attribute == "fire":
        if value == "yes" :
             # Unlock Door.
            print("EXTERNAL FIRE***********************")
           
            # Scan for beacons and add to the sensor data payload.
            beaconsDict = {} #For Payload
            beaconsArray = []
            beacons_detected = beacon_service1.scan(2)
            for beacon_address, beacon_info in list(beacons_detected.items()):
                # For each beacon found, add to the payload. Need to flip the bytes.
                beacon = {
                    "uuid": beacon_info[0].replace('-', ''),
                    "major": (beacon_info[1] % 256) * 256 + beacon_info[1] // 256,
                    "minor": (beacon_info[2] % 256) * 256 + beacon_info[2] // 256,
                    "power": beacon_info[3],
                    "rssi": beacon_info[4],
                    "address": beacon_address
                }
                uuid_temp =  beacon_info[0].replace('-', '')
                address_temp = beacon_address
                major_temp = (beacon_info[1] % 256) * 256 + beacon_info[1] // 256
                minor_temp = (beacon_info[2] % 256) * 256 + beacon_info[2] // 256
                #Add each beacon to the Dictionary
                beaconsArray.append(beacon)
                #StudentID will be configured as beacon MinorID for indentification
                studentIDsInArea1 = studentIDsInArea1 + str(minor_temp) + ","

            #Format String for output
            studentIDsInArea1 = studentIDsInArea1[:-1]
            
            #Actuate LCD - Command Center
            AlertText = "Assist@:"+doorLocation+" StuIDs:"+studentIDsInArea1 
            #AlertText = "External Fire!\nAll Doors Unlock!"
            setText(AlertText)
            setRGB(0,128,64)
            for c in range(0,255):
                setRGB(c,255-c,0)
                time.sleep(0.01)
            setRGB(0,255,0)
            setRGB(0,0,0)

            #Update G49Trace
            grovepi.digitalWrite(relay,0) #open door, cut power to relay
           # grovepi.digitalWrite(led, 0) #LED OFF - Simulate Door LED
            time.sleep(10) #Door left open number of seconds
            grovepi.digitalWrite(relay,1) #lock door, resume power to relay 
           # grovepi.digitalWrite(led, 1)#LED ON - Simulate Door LED

           #Clear LCD
            setText("")
            
           #Update G49Trace
            send_reported_state(client, attribute, value, doorLocation)
            return   
        elif value == "no":
            # Lock Door
            grovepi.digitalWrite(relay,1)#lock door, resume power to relay 
           # grovepi.digitalWrite(led, 1)#LED ON - Simulate Door LED
            send_reported_state(client, attribute, value, doorLocation)
            return
    # Show an error if attribute or value are incorrect.
    print("Error: Don't know how to set " + attribute + " to " + value)


# Control my actuators based on the specified attribute and value,
# "fireStudentIDsInArea= xxx ", we send details to Command Center LCD.
def internalFireActuateDoorNLCD(client, attribute, value, doorLocation):
    if attribute == "timestamp":
        # Ignore the timestamp attribute, it's only for info.
        return
    print("Setting " + attribute + " to " + value + "...")

    if attribute == "studentIDsInArea":
            print("INTERNAL FIRE***********************")
            print("COMMAND CENTER LCD******************************")
            #Actuate LCD - Command Center
            AlertText = "Fire:"+doorLocation+" StuIDs:"+value 
            #AlertText = "Fire!"+doorLocation+"StudentIDs\n:"+value 
            setText(AlertText)
            setRGB(0,128,64)
            for c in range(0,255):
                setRGB(c,255-c,0)
                time.sleep(0.01)
            setRGB(0,255,0)
            #setText("")
            setRGB(0,0,0)

            # Unlock Door.
            grovepi.digitalWrite(relay,0) #open door, cut power to relay
           # grovepi.digitalWrite(led, 0) #LED OFF - Simulate Door LED
            time.sleep(10) #Door left open number of seconds
            grovepi.digitalWrite(relay,1) #lock door, resume power to relay 

            #Clear LCD
            setText("")
            
            #Update G49Trace
            send_reported_state(client, attribute, value, doorLocation)
            return   
# Show an error if attribute or value are incorrect.
    print("Error: Don't know how to set " + attribute + " to " + value)

# Control my actuators based on the specified attribute and value,
# "lockStatus=unlock", we unlock the Door.
def actuateDoor(client, attribute, value, doorLocation):        
    #From Lambda Function: g49_ActuateDoor will update G49Trace desired state. 
    if attribute == "lockStatus":
        if value == "unlock" :
             # Unlock Door.
            print("Authorised User")
            #Actuate LCD Feedback
            AlertText = "Unlock Door:"+doorLocation+" StuID:"+value  
            setText(AlertText)
            setRGB(0,128,64)
            for c in range(0,255):
                setRGB(c,255-c,0)
                time.sleep(0.01)
            setRGB(0,255,0)
            #setText("")
            setRGB(0,0,0)
            #Update G49Trace
            grovepi.digitalWrite(relay,0) #open door, cut power to relay
           # grovepi.digitalWrite(led, 0) #LED OFF - Simulate Door LED
            time.sleep(10) #Door left open number of seconds
            grovepi.digitalWrite(relay,1) #lock door, resume power to relay 
           # grovepi.digitalWrite(led, 1)#LED ON - Simulate Door LED

           #Clear LCD
            setText("")
            
           #Update G49Trace
            send_reported_state(client, attribute, value, doorLocation)
            return   
        elif value == "lock":
            # Lock Door
            grovepi.digitalWrite(relay,1)#lock door, resume power to relay 
           # grovepi.digitalWrite(led, 1)#LED ON - Simulate Door LED
            send_reported_state(client, attribute, value, doorLocation)
            return
    # Show an error if attribute or value are incorrect.
    print("Error: Don't know how to set " + attribute + " to " + value)

# Send the reported state of our actuator to AWS IoT (G49Trace) after it has been triggered, e.g. "lockStatus=unlock"
def send_reported_state(client, attribute, value, doorLocation):
    # Prepare our sensor data in JSON format.
    payload = {
        "state": {
            "reported": {
                "doorLocation": doorLocation,
                attribute: value,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }
    }
    print("Sending sensor data to AWS IoT...\n" +
          json.dumps(payload, indent=4, separators=(',', ': ')))

    # Publish our sensor data to AWS IoT via the MQTT topic, also known as updating our "Thing Shadow".
    # Update G49Trace
    client.publish("$aws/things/g49Trace/shadow/update", json.dumps(payload))
    print("Sent to AWS IoT")


# Print out log messages for tracing.
def on_log(client, userdata, level, buf):
    print("Log: " + buf)


# Start the main program.
main()
