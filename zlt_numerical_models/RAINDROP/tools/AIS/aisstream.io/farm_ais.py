import asyncio
import websockets
import json
from datetime import datetime, timezone
import subprocess
import csv
import os

# Define here your API key from aisstream.io
apikey = ''

# Define here the bounding box
bounding_box = [[[37.8, -9.5], [38.75, -8.5]]]

async def connect_ais_stream(filePath_pr, filePath_sd):

    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
                                "APIKey": apikey,
                                "BoundingBoxes": bounding_box,
                                "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
                            }

        subscribe_message_json = json.dumps(subscribe_message)
        await websocket.send(subscribe_message_json)

        async for message_json in websocket:
            message = json.loads(message_json)
            message_type = message["MessageType"]

            if message_type == "PositionReport":
                # the message parameter contains a key of the message type which contains the message itself
                ais_message = message['Message']['PositionReport']
                print(f"[{datetime.now(timezone.utc)}] ShipId: {ais_message['UserID']} Latitude: {ais_message['Latitude']} Latitude: {ais_message['Longitude']} Speed-Over-Ground: {ais_message['Sog']}")

                ais_data = [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                            ais_message['MessageID'],
                            ais_message['RepeatIndicator'],
                            ais_message['UserID'],
                            ais_message['Valid'],
                            ais_message['NavigationalStatus'],
                            ais_message['RateOfTurn'],
                            ais_message['Sog'],
                            ais_message['PositionAccuracy'],
                            ais_message['Longitude'],
                            ais_message['Latitude'],
                            ais_message['Cog'],
                            ais_message['TrueHeading'],
                            ais_message['Timestamp'],
                            ais_message['SpecialManoeuvreIndicator'],
                            ais_message['Spare'],
                            ais_message['Raim'],
                            ais_message['CommunicationState']]
                with open(filePath_pr, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(ais_data)



            if message_type == "ShipStaticData":
                # the message parameter contains a key of the message type which contains the message itself
                ais_message = message['Message']['ShipStaticData']
                print(f"[{datetime.now(timezone.utc)}] ShipId: {ais_message['UserID']} Name: {ais_message['Name']}")

                ais_data = [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                            ais_message['MessageID'],
                            ais_message['RepeatIndicator'],
                            ais_message['UserID'],
                            ais_message['Valid'],
                            ais_message['AisVersion'],
                            ais_message['ImoNumber'],
                            ais_message['CallSign'],
                            ais_message['Name'],
                            ais_message['Type'],
                            ais_message['Dimension']['A'],
                            ais_message['Dimension']['B'],
                            ais_message['Dimension']['C'],
                            ais_message['Dimension']['D'],
                            ais_message['FixType'],
                            ais_message['Eta']['Day'],
                            ais_message['Eta']['Hour'],
                            ais_message['Eta']['Minute'],
                            ais_message['Eta']['Month'],
                            ais_message['MaximumStaticDraught'],
                            ais_message['Destination'],
                            ais_message['Dte'],
                            ais_message['Spare']]
                with open(filePath_sd, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(ais_data)


if __name__ == "__main__":

    if not os.path.exists('./ais'): os.makedirs('./ais')

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    #Create new csv to store position report
    filePath_pr = './ais/ais_PositionReport_{}.csv'.format(now)
    subprocess.run(['touch', filePath_pr])

    #Create new csv to store position report
    filePath_sd = './ais/ais_ShipStaticData_{}.csv'.format(now)
    subprocess.run(['touch', filePath_sd])

    #Write first line, with headers
    header_pr = ['WriteTime', 'MessageID', 'RepeatIndicator', 'UserID',
              'Valid', 'NavigationalStatus', 'RateOfTurn', 'Sog',
              'PositionAccuracy', 'Longitude', 'Latitude', 'Cog',
              'TrueHeading', 'Timestamp', 'SpecialManoeuvre', 'Spare',
              'Raim', 'CommunicationState']
    header_sd = ['WriteTime', 'MessageID', 'RepeatIndicator', 'UserID', 'Valid',
              'AisVersion', 'ImoNumber', 'CallSign', 'Name',
              'Type', 'DimensionA', 'DimensionB', 'DimensionC',
              'DimensionD', 'FixType', 'EtaDay', 'EtaHour', 'EtaMinute', 'EtaMonth','MaximumStaticDraught', 'Destination', 'Dte', 'Spare']
    
    with open(filePath_pr, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header_pr)

    with open(filePath_sd, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header_sd)

    #Get AIS and immediately write it to csv file
    asyncio.run(connect_ais_stream(filePath_pr, filePath_sd))
