import os
import sys
import socket
import pickle
import time
import rsa
import threading
import random
from threading import Thread
from raftutility import *
import random


BUFF_SIZE = 20480
C2C_CONNECTIONS = {}
CLIENT_STATE = None
MessageQueue = []

def sleep():
    time.sleep(3)


class Server(Thread):
    def __init__(self):
        Thread.__init__(self)
    
    def run(self):
        print("Inside server")
        if(pid==1):
            try:
                for i in range(2,6):
                    print("Sending msg to ", i)
                    #time.sleep(random.randint(1,3))
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[i]].send(pickle.dumps(["hello"]))
                    print("Msg sent to ", i)
            except Exception as e:
                print("Exception caught ",e)
        



class ClientConnections(Thread):
    def __init__(self, client_id, connection):
        Thread.__init__(self)
        self.client_id = client_id
        self.connection = connection

    def run(self):
        #print("Waiting for messages")
        while True:
            try:
                resp = self.connection.recv(BUFF_SIZE)
                data = pickle.load(resp)
                #print("Received data: ", data)
                MessageQueue.append(data)
            
            except Exception as e:
                #print("Exception received: ",e)
                CLIENT_STATE.active_link[self.client_id] = False
                self.connection.close()
                break


class AcceptConnections(Thread):
    def __init__(self, ip, listen_port):
        Thread.__init__(self)
        self.ip=ip
        self.listen_port = listen_port

    def run(self):
        print('Waiting for connections')
        client2client = socket.socket()
        client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client2client.bind((self.ip, self.listen_port))
        client2client.listen(5)

        while True:
            #print('Waiting for connections')
            conn, client_add = client2client.accept()    
            print('Connected to: ' + client_add[0]+':'+client_add[1])
            C2C_CONNECTIONS[client_add[1]]= conn
            temp= client_add[1]
            one = temp % 10
            two = int(temp/10)
            two = two%10
            client = one + two - CLIENT_STATE.pid
            CLIENT_STATE.active_link[client] = True
            #clientConnection has to be made
            new_client = ClientConnections(client, conn)
            new_client.daemon = True
            new_client.start()
    


class Client:
    def __init__(self, pid, listen_port, port_mapping, file_path):
        self.pid = pid
        self.listen_port = listen_port
        self.port_mapping = port_mapping
        self.file_path = file_path
        self.ip = '127.0.0.1'

    def start_client(self):
        global CLIENT_STATE

        if os.path.exists(self.file_path):
            with open(self.file_path, "rb") as f:
                if(os.stat(self.file_path).st_size!=0):
                    print("LOADING SAVED STATE FROM LOGS")
                    CLIENT_STATE = pickle.load(f.read()) #what is the type of CLIENT_STATE here
                    CLIENT_STATE.last_recv_time = time.time()
                    CLIENT_STATE.active_link = {1: False, 2:False, 3:False, 4:False, 5:False}
                    CLIENT_STATE.votes ={}
                    for entry in CLIENT_STATE.logs:
                        print(str(entry))
                    f.close()

        #accept connections from
        # higher numbered process and send connections to lower numbered processes
        # sending connection request to lower numbered proceess
        print(self.port_mapping)
        
        for i in range(1, self.pid):
            #send connection request
            #  
            port = self.port_mapping[i]
            client2client = socket.socket()
            client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            client2client.bind((self.ip, port))

            try:
                print("Sending Connection Request to ", i)
                connect_to = 7000 + i
                client2client.connect((self.ip,connect_to))
                print('Connected to Client ' + str(i) + 'on' + self.ip + ':' + str(connect_to) + ' from port ' + str(port))
                C2C_CONNECTIONS[port] = client2client
                CLIENT_STATE.active_link[i]=True
                new_connection = ClientConnections(i, client2client)
                new_connection.daemon= True
                new_connection.start() # new connection is always ready to receive
            except socket.error as e:
                print(str(e))

        # accept connections from i+1 till 5
        print('Waiting for connections')
        client2client = socket.socket()
        client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client2client.bind((self.ip, self.listen_port))
        client2client.listen(5)

        j=self.pid+1
        while(j<6):
            conn, client_add = client2client.accept()    
            print('Connected to: ' + str(client_add[0])+':'+str(client_add[1]))
            C2C_CONNECTIONS[client_add[1]]= conn
            temp= client_add[1]
            one = temp % 10
            two = int(temp/10)
            two = two%10
            client = one + two - CLIENT_STATE.pid
            CLIENT_STATE.active_link[client] = True
            #clientConnection has to be made
            new_client = ClientConnections(client, conn)
            new_client.daemon = True
            new_client.start()
            j+=1

        print("All connections successfull")
        '''
        #need to comment later
        accept_connections = AcceptConnections(self.ip, self.listen_port)
        accept_connections.daemon = True
        accept_connections.start()

        self.connect_to_peers()
        
        print("All connections successful")
        '''
        server_thread = Server()
        #server_thread.daemon = True
        server_thread.start()

        #persistant thread


    def connect_to_peers(self):

        for client_id in self.port_mapping:
            port = self.port_mapping[client_id] #eg: 7012,7013....7023 etc

            client2client = socket.socket()
            client2client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            client2client.bind((self.ip, port)) 

            try:
                connect_to = 7000 + client_id
                client2client.connect(self.ip,connect_to)
                print('Connected to Client ' + client_id + 'on' + self.ip + ':' + str(connect_to) + 'from port ' + str(port))
                C2C_CONNECTIONS[port] = client2client
                CLIENT_STATE.active_link[client_id]=True
                new_connection = ClientConnections(client_id, client2client)
                new_connection.daemon= True
                new_connection.start() # new connection is always ready to receive
            except:
                a=1

    def broadcast(self, append_entry):
        if CLIENT_STATE.curr_state == "LEADER":
            MessageQueue.append(append_entry)
        
        else:
            sleep()
            C2C_CONNECTIONS[CLIENT_STATE.port_mapping[CLIENT_STATE.curr_leader]].send(pickle.dumps(append_entry))
            



if __name__=="__main__":
    listen_port = 0
    pid = 0
    file_path=""

    if sys.argv[1] == "p1":
        listen_port = 7001
        pid=1
        file_path = os.path.join(os.getcwd(),'log/c1.txt')
        port_mapping = {2:7012, 3:7013, 4:7014, 5:7015}

    elif sys.argv[1] == "p2":
        listen_port = 7002
        pid=2
        file_path = os.path.join(os.getcwd(),'log/c1.txt')
        port_mapping = {1:7012, 3:7023, 4:7024, 5:7025}

    elif sys.argv[1] == "p3":
        listen_port = 7003
        pid=3
        file_path = os.path.join(os.getcwd(),'log/c1.txt')
        port_mapping = {1:7013, 2:7023, 4:7034, 5:7035}

    elif sys.argv[1] == "p4":
        listen_port = 7004
        pid=4
        file_path = os.path.join(os.getcwd(),'log/c1.txt')
        port_mapping = {1:7014, 2:7024, 3:7034, 5:7045}
    
    elif sys.argv[1] == "p5":
        listen_port = 7005
        pid=5
        file_path = os.path.join(os.getcwd(),'log/c1.txt')
        port_mapping = {1:7015, 2:7025, 3:7035, 4:7045}

    os.makedirs(os.path.dirname(file_path), exist_ok=True)


    CLIENT_STATE = ClientState(pid, port_mapping, file_path)

    #need to start timer.

    for i in range(1,6):
        #print(os.getcwd())
        key_path = os.path.join(os.getcwd(),'keys/public'+str(i)+'.pem')
        with open(key_path) as f:
            CLIENT_STATE.public_keys[i]= rsa.PublicKey.load_pkcs1(f.read().encode('utf8'))
            f.close()
        
        if i == pid:
            key_path = os.path.join(os.getcwd(),'keys/private'+str(i)+'.pem')
            with open(key_path) as f:
                CLIENT_STATE.private_key = rsa.PrivateKey.load_pkcs1(f.read().encode('utf8'))
                f.close()

    #print("ListenPort:",listen_port)
    client = Client( pid,listen_port ,port_mapping, file_path)
    client.start_client()



