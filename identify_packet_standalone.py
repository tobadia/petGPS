# Local tests with hard-coded content for requests, to test
# identification of data while my sockets may be busy

def identify_packet(packet):
    print("Original packet     :", packet)
    print("Length of packet    :", len(packet))
    #print("Bytes from Hex                :", bytes.fromhex(packet))
    #print("Length of Bytes from Hex      :", len(bytes.fromhex(packet)))
    #print("ByteArray from Hex                :", bytearray.fromhex(packet))
    #print("Length of ByteArray from Hex      :", len(bytearray.fromhex(packet)))
    print("Hex from Bytes                :", packet.hex())
    print("Length of Hex from Bytes      :", len(packet.hex()))
    
    # DEBUG: Manually set client value and dictionary
    client = "tmp"

    # Explore Bytes
    #print("-----BYTES-----")
    #for b in bytes.fromhex(packet):
        #print(b, "Type : ", type(b))
        #print(bytes(b))
    #print("-----BYTEARRAY-----")
    #for b in bytearray.fromhex(packet):
    #    print(b, "Type : ", type(b))
    #    print(bytes(b))

    # Convert hex string into list for convenience
    # Strip packet of bits 1 and 2 (start 0x78 0x78) and n-1 and n (end 0x0d 0x0a)
    packet_list = [packet.hex()[i:i+2] for i in range(4, len(packet.hex())-4, 2)]
    
    # DEBUG: Print packet
    #print("-----HEX LIST-----")
    #for h in packet_list:
    #    print(h)
    
    # DEBUG: Print the role of current packet
    protocol_name = protocol_dict['protocol'][packet_list[1]]
    protocol_method = protocol_dict['response_method'][protocol_name]
    print("The current packet is for protocol: " + protocol_name + " which has method: " + protocol_method)
    # If the packet requires a specific response, run the associated function
    if (protocol_method == "login"):
        r = login(client, packet_list)
    elif (protocol_method == "setup"):
        # TODO: HANDLE NON-DEFAULT VALUES
        r = setup(packet_list, '0300', '00110001', '000000', '000000', '000000', '00', '000000', '000000', '000000', '00', '0000', '0000', ['', '', ''])

    # Otherwise, return a generic packet based on the current protocol number
    else:
        r = generic_response(packet_list[1])
    
    # DEBUG: Run login function manually 
    #r = login(packet_list)
    
    print("OUT Hex  : ", r)
    print("OUT Bytes: ", bytes.fromhex(r))

def login(client, q):
    """This function extracts IMEI and Software Version from the login packet. 
    The IMEI and Software Version will be stored into a client dictionary to 
    allow handling of multiple devices at once, in the future.
    
    The client socket is passed as an argument because it is in this packet
    that IMEI is sent and will be stored in the address dictionary.
    """
    
    # Initialize the dictionary
    addresses[client] = {}
    
    # Read data: Bits 2 through 9 are IMEI and 10 is software version
    protocol = q[1]
    addresses[client]['imei'] = q[2] + q[3] + q[4] + q[5] + q[6] + q[7] + q[8] + q[9]
    addresses[client]['software_version'] = q[10]

    # DEBUG: Print IMEI and software version
    print("IMEI : ", addresses[client]['imei'])
    print("Sw v. : ", addresses[client]['software_version'])

    # Prepare response: in absence of control values, 
    # always accept the client
    response = '01'
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, response, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def setup(q, uploadIntervalSeconds, binarySwitch, alarm1, alarm2, alarm3, dndTimeSwitch, dndTime1, dndTime2, dndTime3, gpsTimeSwitch, gpsTimeStart, gpsTimeStop, phoneNumbers):
    """Synchronous setup is initiated by the device who asks the server for 
    instructions.
    These instructions will consists of bits for different flags as well as
    alarm clocks ans emergency phone numbers."""

    # Read protocol
    protocol = q[1]

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


def generic_response(protocol):
    """Many queries made by the device do not expect a complex
    response: most of the times, the device expects the exact same packet.
    Here, we will answer with the same value of protocol that the device sent, 
    not using any content."""
    r = make_content_response(hex_dict['start'] + hex_dict['start'], protocol, None, hex_dict['stop_1'] + hex_dict['stop_2'])
    return(r)


def make_content_response(start, protocol, content, stop):
    """This is just a wrapper to generate the complete response
    to a query, goven its content.
    It will apply to all packets where response is of the format:
    start-start-length-protocol-content-stop_1-stop_2.
    Other specific packets where length is replaced by counters
    will be treated separately."""
    return(start + format((len(bytes.fromhex(content)) if content else 0)+1, '02X') + protocol + (content if content else '') + stop)


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
        '15': 'factory', 
        '16': 'whitelist_total', 
        '17': 'offline_wifi', 
        '30': 'time', 
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
        'supervision': '',
        'heartbeat': '', 
        'gps_positioning': 'datetime_response', 
        'gps_offline_positioning': 'datetime_response', 
        'status': '', 
        'hibernation': '', 
        'factory': '', 
        'whitelist_total': '', 
        'offline_wifi': '', 
        'time': '', 
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


addresses = {}
if __name__ == "__main__":
    hex_login_q = "78780d010359339075016807420d0a"
    identify_packet(bytes.fromhex(hex_login_q))
    hex_setup_q = "787801570d0a"
    identify_packet(bytes.fromhex(hex_setup_q))