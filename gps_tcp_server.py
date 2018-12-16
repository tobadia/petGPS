#!/bin/python

"""
TCP Server for multithreaded (asynchronous) application.

This server implements the protocol documented by the chinese
company TOPIN to handle communication with their GPS trackers,
sending and receiving TCP packets over 2G network.

This program will create a TCP socket and each client will have
its dedicated thread created, so that multipe clients can connect 
simultaneously should this be necessary somedy.

This server is based on the work from:
https://medium.com/swlh/lets-write-a-chat-app-in-python-f6783a9ac170
"""

from dotenv import load_dotenv
from socket import AF_INET, socket, SOCK_STREAM
from threading import Thread
import datetime
import googlemaps
import math
import os


def accept_incoming_connections():
    """
    Accepts any incoming client connexion 
    and starts a dedicated thread for each client.
    """
    
    while True:
        client, client_address = SERVER.accept()
        print('%s:%s has connected.' % client_address)
        
        # Initialize the dictionaries
        addresses[client] = {}
        positions[client] = {}
        
        # Add current client address into adresses
        addresses[client]['address'] = client_address
        Thread(target=handle_client, args=(client,)).start()

def LOGGER(event, filename, ip, client, type, data):
    """
    A logging function to store all input packets, 
    as well as output ones when they are generated.

    There are two types of logs implemented: 
        - a general (info) logger that will keep track of all 
            incoming and outgoing packets,
        - a position (location) logger that will write to a 
            file contianing only results og GPS or LBS data.
    """
    
    with open(os.path.join('./logs/', filename), 'a+') as log:
        if (event == 'info'):
            # TSV format of: Timestamp, Client IP, IN/OUT, Packet
            logMessage = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S') + '\t' + ip + '\t' + client + type + '\t' + data + '\n'
        elif ('./logs/'+event == 'location'):
            # TSV format of: Timestamp, Client IP, GPS/LBS, Validity, Nb Sat, Latitude, Longitude, Accuracy, Speed, Heading
            logMessage = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S') + '\t' + ip + '\t' + client + '\t' + '\t' + '\t'.join(list(str(x) for x in data.values())) + '\n'
        log.write(logMessage)


def handle_client(client):
    """
    Takes client socket as argument. 
    Handles a single client connection, by listening indefinitely for packets.
    """
    
    # Initialize dictionaries for that client
    positions[client]['wifi'] = []
    positions[client]['gsm-cells'] = []
    positions[client]['gsm-carrier'] = {}
    positions[client]['gps'] = {}

    # Keep receiving and analyzing packets until end of time...
    # or until device sends disconnection signal
    keepAlive = True
    while (True):

        # Handle socket errors with a try/except approach
        try:
            packet = client.recv(BUFSIZ)
            if (len(packet) > 0):
                print('[', addresses[client]['address'][0], ']', 'IN Hex  :', packet.hex(), '(length in bytes =', len(packet), ')')
                LOGGER('info', 'server_log.txt', addresses[client]['address'][0], addresses[client]['imei'], 'IN', packet.hex())
                keepAlive = read_incoming_packet(client, packet)
                # Disconnect if client sent disconnect signal
                if (keepAlive is not True):
                    client.close()
                    print('[', addresses[client]['address'][0], ']', 'DISCONNECTED: socket was closed by client.')
                    break

        except:
            client.close()
            break


def read_incoming_packet(client, packet):
    """
    Handle incoming packets to identify the protocol they are related to,
    and then redirects to response functions that will generate the apropriate 
    packet that should be sent back.
    Actual sending of the response packet will be done by an external function.
    """

    # Convert hex string into list for convenience
    # Strip packet of bits 1 and 2 (start 0x78 0x78) and n-1 and n (end 0x0d 0x0a)
    packet_list = [packet.hex()[i:i+2] for i in range(4, len(packet.hex())-4, 2)]
    
    # DEBUG: Print the role of current packet
    protocol_name = protocol_dict['protocol'][packet_list[1]]
    protocol_method = protocol_dict['response_method'][protocol_name]
    print('The current packet is for protocol:', protocol_name, 'which has method:', protocol_method)
    # Get the protocol name and react accordingly
    if (protocol_name == 'login'):
        r = answer_login(client, packet_list)
    
    elif (protocol_name == 'logout'):
        # Exit function returning False to break main while loop in handle_client()
        print('[', addresses[client]['address'][0], ']', 'STATUS : Sent disconnect packet. Disconnecting now.')
        return(False)

    elif (protocol_name == 'gps_positioning' or protocol_name == 'gps_offline_positioning'):
        r = answer_gps(client, packet_list)

    elif (protocol_name == 'status'):
        # Status can sometimes carry signal strength and sometimes not
        if (packet_list[0] == '06'): 
            print('[', addresses[client]['address'][0], ']', 'STATUS : Battery =', int(packet_list[2], base=16), '; Sw v. =', int(packet_list[3], base=16), '; Status upload interval =', int(packet_list[4], base=16))
        elif (packet_list[0] == '07'): 
            print('[', addresses[client]['address'][0], ']', 'STATUS : Battery =', int(packet_list[2], base=16), '; Sw v. =', int(packet_list[3], base=16), '; Status upload interval =', int(packet_list[4], base=16), '; Signal strength =', int(packet_list[5], base=16))
        # Exit function without altering anything
        return(True)
    
    elif (protocol_name == 'hibernation'):
        # Exit function returning False to break main while loop in handle_client()
        print('[', addresses[client]['address'][0], ']', 'STATUS : Sent hibernation packet. Disconnecting now.')
        return(False)

    elif (protocol_name == 'setup'):
        # TODO: HANDLE NON-DEFAULT VALUES
        r = answer_setup(packet_list, '0300', '00110001', '000000', '000000', '000000', '00', '000000', '000000', '000000', '00', '0000', '0000', ['', '', ''])

    elif (protocol_name == 'time'):
        r = answer_time(packet_list)

    elif (protocol_name == 'wifi_positioning' or protocol_name == 'wifi_offline_positioning'):
        r = answer_wifi_lbs(client, packet_list)

    # Otherwise, return a generic packet based on the current protocol number
    # without any content: 
    #    - reset
    #    - 
    else:
        r = generic_response(packet_list[1])
    
    # Send response to client
    print('[', addresses[client]['address'][0], ']', 'OUT Hex :', r, '(length in bytes =', len(bytes.fromhex(r)), ')')
    send_response(client, r)
    # Return True to avoid failing in main while loop in handle_client()
    return(True)


def answer_login(client, query):
    """
    This function extracts IMEI and Software Version from the login packet. 
    The IMEI and Software Version will be stored into a client dictionary to 
    allow handling of multiple devices at once, in the future.
    
    The client socket is passed as an argument because it is in this packet
    that IMEI is sent and will be stored in the address dictionary.
    """
    
    # Read data: Bits 2 through 9 are IMEI and 10 is software version
    protocol = query[1]
    addresses[client]['imei'] = ''.join(query[2:9])[1:]
    addresses[client]['software_version'] = int(query[10], base=16)

    # DEBUG: Print IMEI and software version
    print("Detected IMEI :", addresses[client]['imei'], "and Sw v. :", addresses[client]['software_version'])

    # Prepare response: in absence of control values, 
    # always accept the client
    response = '01'
    # response = '44'
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_setup(query, uploadIntervalSeconds, binarySwitch, alarm1, alarm2, alarm3, dndTimeSwitch, dndTime1, dndTime2, dndTime3, gpsTimeSwitch, gpsTimeStart, gpsTimeStop, phoneNumbers):
    """
    Synchronous setup is initiated by the device who asks the server for 
    instructions.
    These instructions will consists of bits for different flags as well as
    alarm clocks ans emergency phone numbers.
    """
    
    # Read protocol
    protocol = query[1]

    # Convert binarySwitch from byte to hex
    binarySwitch = format(int(binarySwitch, base=2), '02X')

    # Convert phone numbers to 'ASCII' (?) by padding each digit with 3's and concatenate
    for n in range(len(phoneNumbers)):
        phoneNumbers[n] = bytes(phoneNumbers[n], 'UTF-8').hex()
    phoneNumbers = '3B'.join(phoneNumbers)

    # Build response
    response = uploadIntervalSeconds + binarySwitch + alarm1 + alarm2 + alarm3 + dndTimeSwitch + dndTime1 + dndTime2 + dndTime3 + gpsTimeSwitch + gpsTimeStart + gpsTimeStop + phoneNumbers
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_time(query):
    """
    Time synchronization is initiated by the device, which expects a response
    contianing current datetime over 7 bytes: YY YY MM DD HH MM SS.
    This function is a wrapper to generate the proper response
    """
    
    # Read protocol
    protocol = query[1]

    # Get current date and time into the pretty-fied hex format
    response = get_hexified_datetime()

    # Build response
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_gps(client, query):
    """
    GPS positioning can come into two packets that have the exact same structure, 
    but protocol can be 0x10 (GPS positioning) or 0x11 (Offline GPS positioning)... ?
    Anyway: the structure of these packets is constant, not like GSM or WiFi packets
    """

    # Reset positions lists (Wi-Fi, and LBS) and dictionary (carrier) for that client
    positions[client]['gps'] = {}

    # Read protocol
    protocol = query[1]

    # Extract datetime from incoming query to put into the response
    dt = ''.join(query[2:7])

    # Read in the incoming GPS positioning
    # Byte 8 contains length of packet on 1st char and number of satellites on 2nd char
    gps_data_length = int(query[8][0], base=16)
    gps_nb_sat = int(query[8][1], base=16)
    # Latitude and longitude are both on 4 bytes, and were multiplied by 30000
    # after being converted to seconds-of-angle. Let's convert them back to degree
    gps_latitude = int(''.join(query[9:13]), base=16) / (30000 * 60)
    gps_longitude = int(''.join(query[13:17]), base=16) / (30000 * 60)
    # Speed is on the next byte
    gps_speed = int(query[17], base=16)
    # Last two bytes contain flags in binary that will be interpreted
    gps_flags = format(int(''.join(query[18:20]), base=16), '0>16b')
    position_is_valid = gps_flags[3]
    # Flip sign of GPS latitude if South, longitude if West
    if (gps_flags[4] == '1'):
        gps_latitude = -gps_latitude
    if (gps_flags[5] == '0'):
        gps_longitude = -gps_longitude
    gps_heading = int(''.join(gps_flags[6:]), base = 2)

    # Store GPS information into the position dictionary and print them
    positions[client]['gps']['method'] = 'GPS'
    positions[client]['gps']['valid'] = position_is_valid
    positions[client]['gps']['nb_sat'] = gps_nb_sat
    positions[client]['gps']['latitude'] = gps_latitude
    positions[client]['gps']['longitude'] = gps_longitude
    positions[client]['gps']['accuracy'] = 0.0
    positions[client]['gps']['speed'] = gps_speed
    positions[client]['gps']['heading'] = gps_heading
    print('[', addresses[client]['address'][0], ']', "POSITION/GPS : Valid =", position_is_valid, "; Nb Sat =", gps_nb_sat, "; Lat =", gps_latitude, "; Long =", gps_longitude, "; Speed =", gps_speed, "; Heading =", gps_heading)
    LOGGER('location', 'location_log.txt', addresses[client]['address'][0], addresses[client]['imei'], '', positions[client]['gps'])

    # Get current datetime for answering
    response = get_hexified_datetime()
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def answer_wifi_lbs(client, query):
    """
    iFi + LBS data can come into two packets that have the exact same structure, 
    but protocol can be 0x17 or 0x69. Likely similar to GPS/offline GPS... ?
    Packet structure is variable and consist in N WiFi hotspots (3 <= N <= 8) and
    N (2 <= N <= ?) GSM towers.

    WiFi hotspots are identified by BSSID (mac address; 6 bytes) and RSSI (1 byte).

    GSM is firest defined as MCCMNC (2+1 bytes) and nearby towers are then 
    identified by LAC (2 bytes), Cell ID (2 bytes) and MCISS (1 byte).

    This function will not return anything but write to a dictionary that is accessible
    outside of the function. This is because WiFi/LBS packets expect two responses :
    - hexified datetime
    - decoded positions as latitude and longitude, based from transmitted elements.
    """

    # Reset positions lists (Wi-Fi, and LBS) and dictionary (carrier) for that client
    positions[client]['wifi'] = []
    positions[client]['gsm-cells'] = []
    positions[client]['gsm-carrier'] = {}
    positions[client]['gps'] = {}

    # Read protocol
    protocol = query[1]

    # Datetime is BCD-encoded in bytes 2:7, meaning it's read *directly* as YY MM DD HH MM SS
    # and does not need to be decoded from hex. YY value above 2000.
    dt = ''.join(query[2:8])

    # WIFI
    n_wifi = int(query[0])
    if (n_wifi > 0):
        for i in range(n_wifi):
            current_wifi = {'macAddress': ':'.join(query[(8 + (7 * i)):(8 + (7 * (i + 1)) - 2 + 1)]), # That +1 is because l[start:stop] returnes elements from start to stop-1...
                            'signalStrength': -int(query[(8 + (7 * (i + 1)) - 1)], base = 16)}
            positions[client]['wifi'].append(current_wifi)
            
            # Print Wi-Fi hotspots into the logs
            print('[', addresses[client]['address'][0], ']', "POSITION/WIFI : BSSID =", current_wifi['macAddress'], "; RSSI =", current_wifi['signalStrength'])

    # GSM Cell towers
    n_gsm_cells = int(query[(8 + (7 * n_wifi))])
    # The first three bytes after n_lbs are MCC(2 bytes)+MNC(1 byte)
    gsm_mcc = int(''.join(query[((8 + (7 * n_wifi)) + 1):((8 + (7 * n_wifi)) + 2 + 1)]), base=16)
    gsm_mnc = int(query[((8 + (7 * n_wifi)) + 3)], base=16)
    positions[client]['gsm-carrier']['n_gsm_cells'] = n_gsm_cells
    positions[client]['gsm-carrier']['MCC'] = gsm_mcc
    positions[client]['gsm-carrier']['MNC'] = gsm_mnc

    if (n_gsm_cells > 0):
        for i in range(n_gsm_cells):
            current_gsm_cell = {'locationAreaCode': int(''.join(query[(((8 + (7 * n_wifi)) + 4) + (5 * i)):(((8 + (7 * n_wifi)) + 4) + (5 * i) + 1 + 1)]), base=16),
                                'cellId': int(''.join(query[(((8 + (7 * n_wifi)) + 4) + (5 * i) + 1 + 1):(((8 + (7 * n_wifi)) + 4) + (5 * i) + 2 + 1 + 1)]), base=16),
                                'signalStrength': -int(query[(((8 + (7 * n_wifi)) + 4) + (5 * i) + 2 + 1 + 1)], base=16)}
            positions[client]['gsm-cells'].append(current_gsm_cell)
            
            # Print LBS data into logs as well
            print('[', addresses[client]['address'][0], ']', "POSITION/LBS : LAC =", current_gsm_cell['locationAreaCode'], "; CellID =", current_gsm_cell['cellId'], "; MCISS =", current_gsm_cell['signalStrength'])

    # Build first stage of response with dt and send it to devices
    r_1 = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, dt, hex_dict['stop_1'] + hex_dict['stop_2'])
    print('[', addresses[client]['address'][0], ']', 'OUT Hex :', r_1, '(length in bytes =', len(bytes.fromhex(r_1)), ')')
    send_response(client, r_1)
    
    # Build second stage of response, which requires decoding the positioning data
    print("Decoding location-based data using Google Maps Geolocation API...")
    decoded_position = GoogleMaps_geolocation_service(gmaps, positions[client])
    
    # Handle errors in decoding location
    if (list(decoded_position.keys())[0] == 'error'):
        positions[client]['gps']['method'] = 'LBS'
        positions[client]['gps']['valid'] = 0
        positions[client]['gps']['nb_sat'] = ''
        positions[client]['gps']['latitude'] = ''
        positions[client]['gps']['longitude'] = ''
        positions[client]['gps']['accuracy'] = ''
        positions[client]['gps']['speed'] = ''
        positions[client]['gps']['heading'] = ''
    
    else:
        # We will need to pad latitude and longitude with + sign if missing
        positions[client]['gps']['method'] = 'LBS'
        positions[client]['gps']['valid'] = 1
        positions[client]['gps']['nb_sat'] = ''
        positions[client]['gps']['latitude'] = '{0:{1}}'.format(decoded_position['location']['lat'], '+' if decoded_position['location']['lat'] else '')
        positions[client]['gps']['longitude'] = '{0:{1}}'.format(decoded_position['location']['lng'], '+' if decoded_position['location']['lng'] else '')
        positions[client]['gps']['accuracy'] = decoded_position['accuracy']
        positions[client]['gps']['speed'] = ''
        positions[client]['gps']['heading'] = ''
    LOGGER('location', 'location_log.txt', addresses[client]['address'][0], addresses[client]['imei'], '', positions[client]['gps'])

    # And return the second stage of response, which will be sent in the handle_package() function
    response = '2C'.join([bytes(positions[client]['gps']['latitude'], 'UTF-8').hex(), bytes(positions[client]['gps']['longitude'], 'UTF-8').hex()])
    r_2 = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r_2)


def generic_response(protocol):
    """
    Many queries made by the device do not expect a complex
    response: most of the times, the device expects the exact same packet.
    Here, we will answer with the same value of protocol that the device sent, 
    not using any content.
    """
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, None, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def make_content_response(start, protocol, content, stop):
    """
    This is just a wrapper to generate the complete response
    to a query, goven its content.
    It will apply to all packets where response is of the format:
    start-start-length-protocol-content-stop_1-stop_2.
    Other specific packets where length is replaced by counters
    will be treated separately.
    """
    return(start + format((len(bytes.fromhex(content)) if content else 0)+1, '02X') + protocol + (content if content else '') + stop)


def send_response(client, response):
    """
    Function to send a response packet to the client.
    """
    LOGGER('info', 'server_log.txt', addresses[client]['address'][0], addresses[client]['imei'], 'OUT', response)
    client.send(bytes.fromhex(response))


def get_hexified_datetime():
    """
    Make a fancy function that will return current GMT datetime as hex
    concatenated data, using 2 bytes for year and 1 for the rest.
    The returned string is YY YY MM DD HH MM SS.
    """

    # Get current GMT time into a list
    dt = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S').split("-")
    # Then convert to hex with 2 bytes for year and 1 for the rest
    dt = [ format(int(x), '0'+str(len(x))+'X') for x in dt ]
    return(''.join(dt))


def GoogleMaps_geolocation_service(gmapsClient, positionDict):
    """
    This wrapper function will query the Google Maps API with the list
    of cell towers identifiers and WiFi SSIDs that the device detected.
    It requires a Google Maps API key.
    
    For now, the radio_type argument is forced to 'gsm' because there are 
    no CDMA cells in France (at least that's what I believe), and since the
    GPS device only handles 2G, it's the only option available.
    The carrier is forced to 'Free' since that's the one for the SIM card
    I'm using, but again this would need to be tweaked (also it probbaly
    doesn't make much of a difference to feed it to the function or not!)
    
    These would need to be tweaked depending on where you live.

    A nice source for such data is available at https://opencellid.org/
    """
    print('Google Maps Geolocation API queried with:', positionDict)
    geoloc = gmapsClient.geolocate(home_mobile_country_code=positionDict['gsm-carrier']['MCC'], 
        home_mobile_network_code=positionDict['gsm-carrier']['MCC'], 
        radio_type='gsm', 
        carrier='Free', 
        consider_ip='true', 
        cell_towers=positionDict['gsm-cells'], 
        wifi_access_points=positionDict['wifi'])

    print('Google Maps Geolocation API returned:', geoloc)
    return(geoloc)

"""
This is a debug block to test the GeoLocation API

gmaps.geolocate(home_mobile_country_code='208', home_mobile_network_code='01', radio_type=None, carrier=None, consider_ip=False, cell_towers=cell_towers, wifi_access_points=None)

## DEBUG: USE DATA FROM ONE PACKET
# Using RSSI
cell_towers = [
    {
        'locationAreaCode': 832,
        'cellId': 51917,
        'signalStrength': -90  
    },
    {
        'locationAreaCode': 768,
        'cellId': 64667,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 24713,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 768,
        'cellId': 53851,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 8021,
        'signalStrength': -100
    },
    {
        'locationAreaCode': 1024,
        'cellId': 62216,
        'signalStrength': -100
    }
]

# Using dummy values in dBm
cell_towers = [
    {
        'locationAreaCode': 832,
        'cellId': 51917,
        'signalStrength': -50  
    },
    {
        'locationAreaCode': 768,
        'cellId': 64667,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 24713,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 768,
        'cellId': 53851,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 8021,
        'signalStrength': -30
    },
    {
        'locationAreaCode': 1024,
        'cellId': 62216,
        'signalStrength': -30
    }
]
"""

# Declare common Hex codes for packets
hex_dict = {
    'start': '78', 
    'stop_1': '0D', 
    'stop_2': '0A'
}

protocol_dict = {
    'protocol': {
        '01': 'login',
        '05': 'supervision',
        '08': 'heartbeat', 
        '10': 'gps_positioning', 
        '11': 'gps_offline_positioning', 
        '13': 'status', 
        '14': 'hibernation', 
        '15': 'reset', 
        '16': 'whitelist_total', 
        '17': 'wifi_offline_positioning', 
        '30': 'time', 
        #'43': 'mom_phone_WTFISDIS?', 
        '43': 'logout', 
        '56': 'stop_alarm', 
        '57': 'setup', 
        '58': 'synchronous_whitelist', 
        '67': 'restore_password', 
        '69': 'wifi_positioning', 
        '80': 'manual_positioning', 
        '81': 'battery_charge', 
        '82': 'charger_connected', 
        '83': 'charger_disconnected', 
        '94': 'vibration_received'
    }, 
    'response_method': {
        'login': 'login',
        'logout': 'logout', 
        'supervision': '',
        'heartbeat': '', 
        'gps_positioning': 'datetime_response', 
        'gps_offline_positioning': 'datetime_response', 
        'status': '', 
        'hibernation': '', 
        'reset': '', 
        'whitelist_total': '', 
        'wifi_offline_positioning': '', 
        'time': 'time_response', 
        'stop_alarm': '', 
        'setup': 'setup', 
        'synchronous_whitelist': '', 
        'restore_password': '', 
        'wifi_positioning': '', 
        'manual_positioning': '', 
        'battery_charge': '', 
        'charger_connected': '', 
        'charger_disconnected': '', 
        'vibration_received': ''
    }
}


# Import dotenv with API keys and initialize API connections
load_dotenv()
GMAPS_API_KEY = os.getenv('GMAPS_API_KEY')
gmaps = googlemaps.Client(key=GMAPS_API_KEY)

# Details about host server
HOST = ''
PORT = 5023
BUFSIZ = 4096
ADDR = (HOST, PORT)

# Initialize socket
SERVER = socket(AF_INET, SOCK_STREAM)
SERVER.bind(ADDR)

# Store client data into dictionaries
addresses = {}
positions = {}

if __name__ == '__main__':
    SERVER.listen(5)
    print("Waiting for connection...")
    ACCEPT_THREAD = Thread(target=accept_incoming_connections)
    ACCEPT_THREAD.start()
    ACCEPT_THREAD.join()
    SERVER.close()