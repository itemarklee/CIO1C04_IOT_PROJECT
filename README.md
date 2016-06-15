

#SMART IoT APPLICATIONS (CIO1C03) FINAL PROJECT
#Part B: Application Documentation & Source Codes (SOFTWARE) 
- Created by Mark Lee

Group Members:
- 1571046J:  LEE YI WEI MARK
- 1571042I:  CHIANG TECK MENG JIM
- 1571149B: GAN GHIM CHIEW WINSTON 

#Installation Steps
- For detailed installation steps, please email 1571046J@student.tp.edu.sg

#Files Description/Purpose
#1. Schematic for AWS IoT
- Purpose: Figure showing overall Schematic for our prototype device (RaspberryPi) and AWS.
  - File: g49AWSRules.jpg

#2. For AWS IoT
- Purpose: The following are required to validate the device to use with AWS IoT.
  - File: aws-iot-rootCA.crt
  - File: tp-iot-certificate.pem.crt
  - File: tp-iot-private.pem.key
  - File: tp-iot-public.pem.key

#3. For GrovePi: 
- Purpose: Our sensors require this file to enable sensing and actuation functions. 
  - File: grovepi.py

#4. For Raspberry Pi Device: 
- Purpose: Script that captures data from our sensors, sends and receives updates to/from AWS IoT & performs actuation.
- Key libraries and functions are explained in the comments of the script. 
  - File: G49send_beacon_data.py 
- Sample Console Logs
  - File: ScriptOutputLogs
- Key events are highlighted below
- 1. Sending detected beacons to AWS IoT:
```
Sending sensor data to AWS IoT...
{
    "state": {
        "reported": {
            "beacons": [
                {
                    "uuid": "b9407f30f5f8466eaff925556b57fe6d",
                    "minor": 9713,
                    "address": "F8:CA:25:F1:83:35",
                    "power": 182,
                    "major": 10150,
                    "rssi": -57
                }
            ],
            "timestamp": "2016-06-13T19:27:40.025905"
        }
    }
}
```
- 2. Valid beacon detected to open door:
```
"state": {
        "reported": {
            "message": "Valid beacon to open Door",
            "authorised": true,
            "doorLocation": "Door1"
        }
    },
```
- 3. No valid beacon detected to open door:
```
"state": {
        "reported": {
            "message": "No valid beacon found to open Door",
            "authorised": false,
            "doorLocation": "Door1"
        }
    },
```
- 4. Setting Door lock status to unlock (Actuation):
```
"state": {
        "desired": {
            "timestamp": "2016-06-13T19:27:40.616887",
            "lockStatus": "unlock",
            "doorLocation": "Door1"
        }
    },
```
#5. For AWS Lambda Function (to perform actuation)
- Purpose: Sets desired state for device to act upon and updates to Slack for reporting. 
  - File: g49_ActuateDoor.py
- Extract:
```
    payload = {
        "state": {
            desired_or_reported.lower(): {
                "doorLocation": doorLocation2,
                attribute2: value2,
                "timestamp": timestamp2
            }
        }
    }
```

#6. For AWS Thing/Rules required (Based on Schematic: File: g49AWSRules.jpg)
-1. g49pi (Thing) 
  - Topic: $aws/things/g49pi/shadow/update
  - The Raspberry Pi that contains our Bluetooth low energy (BLE) radio. BLE received detects the beacons.

-2. g49_identify_beacon (Rule) 
  - Topic: $aws/things/g49pi/shadow/update/accepted
  - Monitors g49pi (Thing) and reports whether beacon is authorized via a AWS IoT Republish Action to g49Door1 (Thing) 
  - Query Statement: SELECT CASE get((SELECT * FROM state.reported.beacons WHERE major =10150 AND minor=9713),1).minor WHEN 9713 THEN true ELSE false END AS state.reported.authorised FROM '$aws/things/g49pi/shadow/update/accepted'

-3. g49Door1 (Thing) 
  - Topic: $aws/things/g49Door1/shadow/update
  - Remembers Application State, i,e whether beacon is authorised  	
  - will be updated based on g49pi sensor data
	
-4. g49_alert_authorised_beacon (Rule)
  - Monitors g49Door1 (Thing) and sends a message that beacon is authorised to open door via a AWS IoT Republish Action to g49Trace (Thing).
  - Query Statement: SELECT 'Valid beacon to open Door' as state.reported.message, true as state.reported.authorised, 'Door1' as state.reported.doorLocation FROM '$aws/things/g49Door1/shadow/update/documents' WHERE current.state.reported.authorised = true
   
-5. g49_alert_unauthorised_beacon (Rule)
  - Monitors g49Door1 (Thing) and sends a message that beacon is authorised to open door via a AWS IoT Republish Action to g49Trace (Thing).
  - Query Statement: SELECT ‘No valid beacon to open Door' as state.reported.message, false as state.reported.authorised, 'Door1' as state.reported.doorLocation FROM '$aws/things/g49Door1/shadow/update/documents' WHERE current.state.reported.authorised = false
   
-6. g49Trace (Thing) 
  - Topic: $aws/things/g49Trace/shadow/update 	
  - Used to show debug information when rules are triggered. g49ActuateDoor1(Rule) and g49_record_door1_data (Rule) will monitor this Thing to triggers Rules Actions. 

-7. g49ActuateDoor1(Rule)
  - Monitors g49Trace (Thing) and triggers a Lamda Action (Function name: g49_ActuateDoor) that will sent the desired state for the Raspberry Pi to perform an actuate function. i.e. open the electromagnetic door for the authorised handicap student.
  - Query Statement: SELECT 'g49pi' as device, 'Door1' as doorLocation, 'lockStatus' as attribute, 'unlock' as value, 'desired' as desired_or_reported FROM '$aws/things/g49Trace/shadow/update/accepted' WHERE state.reported.authorised = true
  
-8. g49_record_door1_data (Rule)
  - Monitors g49Trace (Thing) and trigger two Actions
	  - DynamoDB Rule Action (insert into DynamoDB): To write all sensor data updates into a sensor data table to record the sensor data that can be use by our applications.
	  - Lambda Rule Action (Function name: IndexSensorData) for Sumo logic: To write the sensor data into the Sumo Logic search engine to allow us to scan for the data by pattern, and to also generate charts and dashboard to help us understand the data better.
  - Query Statement: SELECT *, version, topic() as topic, traceId() as traceId FROM '$aws/things/g49Trace/shadow/update/accepted'
