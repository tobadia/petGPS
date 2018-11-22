# Original source: https://medium.com/swlh/lets-write-a-chat-app-in-python-f6783a9ac170

"""Server for multithreaded (asynchronous) application."""
from socket import AF_INET, socket, SOCK_STREAM
from threading import Thread


def accept_incoming_connections():
    """Accepts any incoming client connexion 
    and starts a dedicated thread for each client."""
    while True:
        client, client_address = SERVER.accept()
        print("%s:%s has connected." % client_address)
        # No need to send anything
        #client.send(bytes("Greetings from the cave! Now type your name and press enter!", "utf8"))
        addresses[client] = client_address
        Thread(target=handle_client, args=(client,)).start()


def handle_client(client):  # Takes client socket as argument.
    """Handles a single client connection."""

    # Keep receiving and analyzing packets
    while True:
        msg = client.recv(BUFSIZ)
        print("IN: %s" % msg)

        
addresses = {}

HOST = ''
PORT = 5023
BUFSIZ = 1024
ADDR = (HOST, PORT)

SERVER = socket(AF_INET, SOCK_STREAM)
SERVER.bind(ADDR)

if __name__ == "__main__":
    SERVER.listen(5)
    print("Waiting for connection...")
    ACCEPT_THREAD = Thread(target=accept_incoming_connections)
    ACCEPT_THREAD.start()
    ACCEPT_THREAD.join()
    SERVER.close()