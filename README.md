# PetGPS

This is a DIY-project to equip my cat (and hopefully, yours) with a small GPS tracker that is fitted with a SIM card to enable real-time location. There are many commercial alternatives to such a project, but they basically all rely on:
* 2G chipset with nanoSIM slot
* GPS chipset
* Sometimes, WiFi chipset capable of listening to nearby SSIDs (for location-based algorithms)

These commercial alternatives are absolutely overpriced (device 80 EUR as of today + usually charging a montly service fee, ranging from 3 to 8 EUR). In fact, the design is based on cheap knockoff IoT devices available from a well-known chinese wholesale website. The amount of data used by this kind of tracker is minimal (like, __REALLY small__, maybe up to 1 or 2 Mb __per day of use__), and as such, there must be cheaper alternatives to these commercial things... M'kaaaay ?

On the other hand, the chinese alternatives are provided with ugly UI for their ad-hoc services... and I don't want anyone in China to know where my cat goes out!

This repo hosts some developments I have made while using these devices called ZX612 and ZX303 from AliExpress. As of now, it is a complete WIP project, and the code is ugly, but hopefully decently documented. The ultimate goal is to have:
1. A stand-alone Python server that communicates with the device
2. A web UI that reads location logs from the server and shows where my cat has been and when.

Link for purchasing these devices: [ZX612](https://www.aliexpress.com/store/product/Topin-DIY-PCBA-612-Micro-Hidden-Mini-GPS-Tracker-Positioner-Personal-Locator-SOS-Button-Double-Positioning/2968012_32804101835.html) and [ZX303](https://www.aliexpress.com/store/product/New-ZX303-PCBA-GPS-Tracker-GSM-GPS-Wifi-LBS-Locator-SOS-Alarm-Web-APP-Tracking-TF/2968012_32826849478.html) (The ZX303 has more feature for the same size and I'd go with that one). If you want a battery included, order the versions with small plastic casing.

## Protocol documentation
The protocol documentation for these devices is extremely poorly written. It was sent to me by the seller in the form of a Word document, available in the [resources folder](../resources/ZhongXun%20Topin%20Locator%20Communication%20Protocol-180612.docx). It seems to be derived from the [GT06 protocol](../resources/GT06_GPS_Tracker_Communication_Protocol_v1.8.1.pdf), also documented in the same directory. I have _somewhat_ re-written the documentation into an Excel document where each column represents a byte, for each kind of packet sent or received by the device.

Basically:
1. Device starts and sends a 'hello' packet to the server
2. Server acknowledges the device
3. Device send location-based data (either direct GPS coordinates or proxy informations)
4. Server send proxy informations to a location API; GPS coordinates are acknowledged
5. Repeat

These devices can be controlled by sending them SMS or data packets in the form of hexadecimal strings. The general format is
`7878 XX YY ZZZZ 0D0A`
* `7878`: (2 bytes) start bytes
* `XX`: (1 byte) Data length. For some protocol numbers (see `YY` this is not the length but a parameter, e.g. number of SSIDs for WiFi location-based data)
* `YY`: (1 byte) Protocol number (defining what the data will be)
* `ZZZZ`: (varying length) Long chain of hex data that will be interpreted according to the value of `YY`
* `0D0A`: (2 bytes) Stop bytes

## Google Maps API key with dotenv
Your Google Maps API key is **strictly private**. It should **NEVER** be shared with anyone, as it enables querying the API without further login. An API key made public exposes you to unauthorized use, breach of Google's API Terms of Services, or massive querying possibly rsulting in you having to pay the bill once free queries have been exhausted. You don't want that to happen, do you ?

The `dotenv` Python library is used to import the content of a `.env` file into the environment upon starting the main script. This is convenient to set your private API key in a file that will not make it into the Git repository. 
An empty exemple of this file is available [here](https://github.com/tobadia/petGPS/blob/master/.env.example) in the Git repository. The .gitignore file from this repository is set to *not track* the real `.env` file. As such, you should add your API key in a local copy of .env derived from the example file, e.g. with:

```
cp .env.example .env
vi .env
```

Remember to **not** remove `.env` from the `.gitignore` file !

# Running the server
## Port forwarding
The server is set to run on port TCP 5023. Remember to redirect that port towards the machine that will run the server.

## Start
After you've created the actual `.env` file, you're all set. Just run:
```
python gps_tcp_server.py
```
Data should now be coming in.

## Stop
Ctrl+C twice will kill the current connection and then kill the server.

# Some more README
...to be written here