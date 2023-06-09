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
import hashlib


BUFF_SIZE = 20480
C2C_CONNECTIONS = {}
CLIENT_STATE = None
state_machine =None
MessageQueue = []
port_mapping={}
Dictionaries={}
DictionaryDetails={}
#persistCounter = 0

def sleep():
    time.sleep(3)

def encryptPvtKey(private_key, public_key):
        encKey = []
        encKey.append(rsa.encrypt(str(private_key.n).encode(), public_key))
        encKey.append(rsa.encrypt(str(private_key.e).encode(), public_key))
        encKey.append(rsa.encrypt(str(private_key.d).encode(), public_key))
        encKey.append(rsa.encrypt(str(private_key.p).encode(), public_key))
        encKey.append(rsa.encrypt(str(private_key.q).encode(), public_key))
        return encKey

def decryptPvtKey(enc_key, my_key):
    pvtKey = enc_key 
    n = int(rsa.decrypt(enc_key[0], my_key).decode())
    e = int(rsa.decrypt(enc_key[1], my_key).decode())
    d = int(rsa.decrypt(enc_key[2], my_key).decode())
    p = int(rsa.decrypt(enc_key[3], my_key).decode())
    q = int(rsa.decrypt(enc_key[4], my_key).decode())
    privateKey = rsa.PrivateKey(n, e, d, p, q)
    return privateKey

def encrypt_content(content, public_key):
    enc_cont = rsa.encrypt(content.encode(),public_key)
    return enc_cont

def decrypt_content(enc_content, private_key):
    dec_cont = rsa.decrypt(enc_content, private_key).decode()
    return dec_cont
    

class Dictionary:
    def __init__(self, id, clientIds=None, public_key=None, private_key=None):
        self.id= id
        self.clientIds = clientIds
        self.dict={}
        self.public_key = public_key
        self.private_key = private_key
        
    def addKeyValPair(self, key, val):
        print(key)
        if key not in self.dict:
            self.dict[key] = val
            print("Succesfully added Key-Value pair " + str(key) + ":" + str(val))
            print("Dictionary After adding key-val", self.dict)
            return
        
        else:
            print("Key already present")
            return
        
    def getKeyValPair(self, key):
        if key not in self.dict:
            print("Key "+ str(key) + " not present in dictionary " + str(self.id))
            return
        
        else:
            return self.dict[key]
        
    def __str__(self):
        return str(self.id) + "|" + str(self.clientIds) + "|" + str(self.dict)
        
        


class StateMachine(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.lastCommitIndex = 0 #Starting index from where we need to commit
    
    def run(self):
        while(True):
            try:
                if(self.lastCommitIndex < CLIENT_STATE.commit_index):
                    log_entry = CLIENT_STATE.logs[self.lastCommitIndex+1]
                    # if(log_entry.msg == None):
                    #     print("CommittedIndex:", self.commitIndex)
                    #     self.commitIndex+=1
                    #     continue
                    operation_info = log_entry.msg
                    #print(operation_info)
                    
                    if(operation_info.operation_type == "CREATE_DICT"):
                        print("Create Operation Executing")
                        client_ids = operation_info.client_ids
                        dict_public_key = operation_info.public_key
                        dict_id = operation_info.dict_id
                        
                        try:
                            dict_private_key = decryptPvtKey(operation_info.enc_private_keys[CLIENT_STATE.pid], CLIENT_STATE.private_key)
                        except:
                            print("CREATE_DICT: Decryption of private Key failed, I don't own this Dictionary.")
                        
                        if CLIENT_STATE.pid in client_ids:
                            dict_private_key = decryptPvtKey(operation_info.enc_private_keys[CLIENT_STATE.pid], CLIENT_STATE.private_key)
                            dictionary = Dictionary(dict_id, client_ids)
                            dictionary.public_key= dict_public_key
                            dictionary.private_key = dict_private_key
                            Dictionaries[dict_id]=dictionary
                            print("Dictionary creation successful")
                        
                        #Savingthe public_keys for the dictionary
                        DictionaryDetails[dict_id]=dict_public_key
                
                    else:
                        #need to decrypt and check the operation
                        dict_id = operation_info.dict_id
                        if dict_id in Dictionaries:
                            print("This is the Dictionary that I own, decrypting the operations and necessary keys")
                            operation_type = decrypt_content(operation_info.operation_type, Dictionaries[dict_id].private_key)
                            if(operation_type == "PUT"):
                                print("Put operation executing| dictId: ", dict_id)
                                
                                decrypt_key = decrypt_content(operation_info.key, Dictionaries[dict_id].private_key)
                                decrypt_val = decrypt_content(operation_info.val, Dictionaries[dict_id].private_key)
                                dictionary = Dictionaries[dict_id]
                                dictionary.addKeyValPair(decrypt_key,decrypt_val)
                                print("Addition Successful")
                                
                            elif(operation_type == "GET"):
                                print("Get operation executing| dictId: ", dict_id)
                                decrypt_key = decrypt_content(operation_info.key, Dictionaries[dict_id].private_key)
                                dictionary = Dictionaries[dict_id]
                                print(dictionary.getKeyValPair(decrypt_key))
                                print("Get Operation Successfull")
                                #print(Dictionaries)
                        
                    '''    
                    elif(operation_info.operation_type == "PUT"):
                        dict_id = operation_info.dict_id
                        print("Put operation executing| dictId: ", dict_id, type(dict_id))
                        print(Dictionaries)
                        if(dict_id in Dictionaries):
                            dictionary = Dictionaries[dict_id]
                            dictionary.addKeyValPair(operation_info.key,operation_info.val)
                    
                    elif(operation_info.operation_type == "GET"):
                        dict_id = operation_info.dict_id
                        if(dict_id in Dictionaries):
                            dictionary = Dictionaries[dict_id]
                            print(dictionary.getKeyValPair(operation_info.key))
                    '''
                    print("Executed Index:", self.lastCommitIndex)
                    self.lastCommitIndex+=1
            
            except:
                pass           

class Server(Thread):
    def __init__(self):
        Thread.__init__(self)
    
    def run(self):
        while(True):
            if len(MessageQueue)!=0:
                data = MessageQueue.pop(0)
                
                if data.req_type == "FIX_LINK":
                    CLIENT_STATE.active_link[data.dest] = True 
                    
                elif data.req_type == "FAIL_LINK":
                    CLIENT_STATE.active_link[data.dest] = False
                    
                elif CLIENT_STATE.curr_state == "LEADER":
                    if data.req_type == "REQ_VOTE":
                        print("LEADER: Received vote request from ", str(data.candId))
                        self.ReqVote_Handler_Leader(data)
                        
                    elif data.req_type == "APPEND_ENTRY":
                        print("LEADER: Received Append Entry from ", str(data.leaderId))
                        self.AppendEntry_Handler_Leader(data)
                        
                    elif data.req_type == "RESP_APPEND_ENTRY":
                        print("LEADER: Response on Append Entry received from ", str(data.pid))
                        self.AppendEntryResponse_handler_Leader(data)
                        
                    elif data.req_type == "CLIENT_REQ":
                        print("LEADER: Received new client request")
                        self.ClientRequestHandler_leader(data)
                        
                        
                elif CLIENT_STATE.curr_state == "FOLLOWER":
                    if data.req_type == " REQ_VOTE":
                        print("As FOLLOWER: received Request Vote from "+ str(data.candId))
                        self.ReqVote_Handler_Follower(data)
                    
                    elif data.req_type == "APPEND_ENTRY":
                        print("FOLLOWER: Received Append Entry from " + str(data.leaderId))
                        self.AppendEntry_Handler_Follower(data)
                    
                    elif data.req_type == "CLIENT_REQ":
                        #need to send this to leader
                        pass
                        
                elif CLIENT_STATE.curr_state == "CANDIDATE":
                    if data.req_type == "REQ_VOTE":
                        print("CANDIDATE: Received Vote Request from " + str(data.candId))
                        self.ReqVote_Handler_Follower(data)
                    elif data.req_type == "RESP_VOTE":
                        print("CANDIDATE: Vote Response Received: " +str(data.voteGranted))
                        self.ResponseVoteHandler_Candidate(data)
                    elif data.req_type == "APPEND_ENTRY":
                        print("CANDIDATE: Received Append Entry from " + str(data.leaderId))
                        self.AppendEntry_Handler_Follower(data)
                
    def ReqVote_Handler_Leader(self, data):
        try:
            
            if data.term <= CLIENT_STATE.curr_term:
                #deny the vote
                deny = pickle.dumps(RespVote("RESP_VOTE", CLIENT_STATE.curr_term, False))
                print("LEADER: Rejected Vote request for " + str(data.candId) + " for term " + str(data.term))
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candId]].send(deny)
            else:
                CLIENT_STATE.last_recv_time = time.time()
                CLIENT_STATE.curr_state = "FOLLOWER"
                CLIENT_STATE.curr_term = data.term
                CLIENT_STATE.voted_for = data.candId
                
                accept = pickle.dumps(RespVote("RESP_VOTE", CLIENT_STATE.curr_term, True))
                print("Transitioned to FOLLOWER! Accepted Leader " + str(data.candId) + " for term " + str(data.term))
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candId]].send(accept)
        except:
            pass
            
    def ReqVote_Handler_Follower(self, data):
        try:
            vote = False
            
            if data.term < CLIENT_STATE.curr_term:
                vote = False
            
            else: 
                if data.term  > CLIENT_STATE.curr_term:
                    CLIENT_STATE.curr_term = data.term
                    CLIENT_STATE.voted_for = 0
                    
                if CLIENT_STATE.voted_for == 0 or CLIENT_STATE.voted_for == data.candId:
                    if CLIENT_STATE.logs[-1].term < data.lastLogTerm:
                        vote = True
                    elif CLIENT_STATE.logs[-1].term == data.lastLogTerm and CLIENT_STATE.logs[-1].index <= data.lastLogIndex:
                        vote = True
                    else:
                        vote = False
                else:
                    vote = False
                    
            if vote == True:
                CLIENT_STATE.last_recv_time = time.time()
                CLIENT_STATE.curr_state = "FOLLOWER"
                CLIENT_STATE.curr_term = data.term
                CLIENT_STATE.voted_for = data.candId
                
                accept = pickle.dumps(RespVote("RESP_VOTE", CLIENT_STATE.curr_term, True))
                print("FOLLOWER: Accepted leader "+ str(data.candId) + " for term" + str(data.term))
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candId]].send(accept)
                
            else:
                reject = pickle.dumps(RespVote("RESP_VOTE", CLIENT_STATE.curr_term, False))
                print("Leader Candidate "+ str(data.candId)+ " Rejected for term " + str(data.term))
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.candId]].send(reject) 
        except:
            pass
                
    def AppendEntry_Handler_Leader(self, data):
        try:
            if data.term <= CLIENT_STATE.curr_term:
                response = pickle.dumps(ResponseAppendEntry("RES_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term, False))
                sleep()
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
                
            else:
                CLIENT_STATE.last_recv_time = time.time()
                CLIENT_STATE.curr_leader = data.leaderId
                CLIENT_STATE.curr_state = "FOLLOWER"
                CLIENT_STATE.curr_term = data.term
                CLIENT_STATE.voted_for = 0
                
                if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
                    #same term but lower index
                    if(len(data.entries) > 0):
                        for entry in data.entries:
                            CLIENT_STATE.log.append(entry)
                        CLIENT_STATE.logs = CLIENT_STATE.logs[0: data.endtries[-1].index + 1]
                    elif data.prevLogIndex < len(CLIENT_STATE.logs) -1:
                        CLIENT_STATE.logs = CLIENT_STATE.logs[0: data.prevLogIndex + 1]
                        
                    
                    response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term,True))
                    sleep()
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
                    CLIENT_STATE.commit_index = data.commitIndex
                    
                else:
                    response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term, False))
                    sleep()
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
        except:
            pass
                
    def AppendEntry_Handler_Follower(self, data):
        try:
            if data.term < CLIENT_STATE.curr_term:
                response = pickle.dumps(ResponseAppendEntry("RES_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term, False))
                sleep()
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
                
            else:
                #curr term is less than or equal to
                
                CLIENT_STATE.last_recv_time = time.time()
                CLIENT_STATE.curr_leader = data.leaderId
                CLIENT_STATE.curr_state = "FOLLOWER"
                
                if data.term > CLIENT_STATE.curr_term:
                    CLIENT_STATE.curr_term = data.term
                    # TODO : update to leader
                    CLIENT_STATE.voted_for = 0
                
                if data.prevLogIndex < len(CLIENT_STATE.logs) and CLIENT_STATE.logs[data.prevLogIndex].term == data.prevLogTerm:
                    # TODO: recheck
                    CLIENT_STATE.logs = CLIENT_STATE.logs[:data.prevLogIndex+1]
                    # if data.prevLogIndex < len(CLIENT_STATE.logs) -1:
                    #     CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.prevLogIndex+1]
                    if len(data.entries) > 0:
                        for entry in data.entries:
                            #hashing here
                            
                            CLIENT_STATE.logs.append(entry)
                        # CLIENT_STATE.logs = CLIENT_STATE.logs[0:data.entries[-1].index+1]
                    response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term, True))
                    print("Added {} entries to my log".format(len(data.entries)))
                    sleep()
                    C2C_CONNECTIONS[port_mapping[data.leaderId]].send(response)
                    CLIENT_STATE.commit_index = data.commitIndex
                    
                else:
                    response = pickle.dumps(ResponseAppendEntry("RESP_APPEND_ENTRY", CLIENT_STATE.pid, CLIENT_STATE.curr_term, False))
                    sleep()
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.leaderId]].send(response)
        except:
            pass
        
                
    def AppendEntryResponse_handler_Leader(self, data):
        try:
            if data.success == True:
                CLIENT_STATE.next_index[data.pid] = CLIENT_STATE.logs[-1].index+1
                prevInd = CLIENT_STATE.commit_index + 1
                index = CLIENT_STATE.commit_index + 1
                
                while index <= CLIENT_STATE.logs[-1].index:
                    CLIENT_STATE.log_entry_counts[index].add(data.pid)
                    if len(CLIENT_STATE.log_entry_counts[index]) >=3:
                        if CLIENT_STATE.logs[index].term == CLIENT_STATE.curr_term:
                            CLIENT_STATE.commit_index = index
                    
                    else:
                        break
                    
                    index+=1
                
                while prevInd <= CLIENT_STATE.commit_index:
                    print(str(prevInd) + "COMMITTED")
                    prevInd +=1
                
            else:
                if data.term > CLIENT_STATE.curr_term:
                    CLIENT_STATE.last_recv_time = time.time()
                    CLIENT_STATE.curr_state = "FOLLOWER"
                    CLIENT_STATE.curr_term = data.term
                    CLIENT_STATE.voted_for = 0
                    
                else:
                    CLIENT_STATE.next_index[data.pid] -=1
                    entries = CLIENT_STATE.logs[CLIENT_STATE.next_index[data.pid]:]
                    append_entry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, CLIENT_STATE.logs[CLIENT_STATE.next_index[data.pid]-1].index, \
                        CLIENT_STATE.logs[CLIENT_STATE.next_index[data.pid]-1].term, entries, CLIENT_STATE.commit_index)
                    
                    sleep()
                    
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[data.pid]].send(pickle.dumps(append_entry))
        except:
            pass
                
    def ResponseVoteHandler_Candidate(self, data):
        if data.term > CLIENT_STATE.curr_term:
            CLIENT_STATE.last_recv_time = time.time()
            CLIENT_STATE.curr_state = "FOLLOWER"
            CLIENT_STATE.curr_term = data.term
            CLIENT_STATE.voted_for = 0
            
        else:
            if data.voteGranted == True:
                key = str(CLIENT_STATE.pid) + "|" + str(data.term)
                if key not in CLIENT_STATE.votes:
                    CLIENT_STATE.votes[key]=0
                CLIENT_STATE.votes[key]+=1
                print("Total votes received: ",  CLIENT_STATE.votes[key])
                if CLIENT_STATE.votes[key] >=3:
                    print("MAJORITY VOTES RECEIVED. BECAME LEADER") 
                    CLIENT_STATE.curr_state = "LEADER"
                    for key in CLIENT_STATE.next_index:
                        CLIENT_STATE.next_index[key] = CLIENT_STATE.logs[-1].index +1
                    
                    index = CLIENT_STATE.commit_index+1
                    while(index <= CLIENT_STATE.logs[-1].index):
                        CLIENT_STATE.log_entry_counts[index] = set()
                        CLIENT_STATE.log_entry_counts[index].add(CLIENT_STATE.pid)
                        index+=1
                    
                    #need to add heartbeat  
                    heart_beat_thread = HeartBeat()
                    heart_beat_thread.start() 
                    
    def ClientRequestHandler_leader(self, data):
        try:
            entries = []
            newEntry = LogEntry(CLIENT_STATE.curr_term, len(CLIENT_STATE.logs), data)
            entries.append(newEntry)
            CLIENT_STATE.log_entry_counts[newEntry.index]= set()
            CLIENT_STATE.log_entry_counts[newEntry.index].add(CLIENT_STATE.pid)
            
            append_entry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term,\
                                                                                        entries, CLIENT_STATE.commit_index)
            #hashing here
            '''
            lastLogMsg = CLIENT_STATE.log(len(CLIENT_STATE.log)-1).msg
            hashed_cont = hashlib.sha256(pickle.dumps(lastLogMsg)).digest()
            new_entry = LogEntry(CLIENT_STATE.curr_term, len(CLIENT_STATE.logs), data, hashed_cont)
            CLIENT_STATE.log.append(new_entry)
            '''
            
            CLIENT_STATE.logs.append(newEntry)
            
            CLIENT_STATE.leader_heart_beat = time.time()
            sleep()
            
            for client in CLIENT_STATE.port_mapping:
                if CLIENT_STATE.active_link[client] == True:
                    print("New Log entry for index|term " + str(newEntry.index) + "|" + str(CLIENT_STATE.curr_term) + " sent to " + str(client))
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(append_entry))
        except:
            pass
        
        '''     
        for entry in CLIENT_STATE.logs:
            print(str(entry))
        '''
        

class HeartBeat(Thread):
    def __init__(self, timeout = 20):
        Thread.__init__(self)
        self.timeout = timeout
        
    def run(self):        
        try:
            entry = []
            append_entry = AppendEntry("APPEND_ENTRY", CLIENT_STATE.curr_term, CLIENT_STATE.pid, CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term, entry, \
                CLIENT_STATE.commit_index)
            while CLIENT_STATE.curr_state == "LEADER":
                if time.time() - CLIENT_STATE.leader_heart_beat > self.timeout:
                    CLIENT_STATE.leader_heart_beat = time.time()
                    append_entry.prevLogIndex = CLIENT_STATE.logs[-1].index
                    append_entry.prevLogTerm = CLIENT_STATE.logs[-1].term
                    append_entry.commitIndex = CLIENT_STATE.commit_index
                    print("SENDING HEARTBEAT")
                    for client in CLIENT_STATE.port_mapping:
                        if CLIENT_STATE.active_link[client] == True:
                            C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(append_entry))
        except:
            pass
                                 

class Timer(Thread):
    def __init__(self, timeout):
        Thread.__init__(self)
        self.timeout = timeout
        
    def run(self):
        while(True):
            try:
                
                if time.time() - CLIENT_STATE.last_recv_time > self.timeout and CLIENT_STATE.curr_state != "LEADER":
                    CLIENT_STATE.last_recv_time = time.time()
                    print("Starting Leader Election")
                    self.start_election()
                    self.timeout = random.randint(25, 50)
                    #New timeout set
                    print("NEW TIMEOUT = " + str(self.timeout))
                    
            except:
                pass
                
                
    def start_election(self):
        try:
            CLIENT_STATE.curr_state = "CANDIDATE"
            CLIENT_STATE.curr_leader = CLIENT_STATE.pid
            CLIENT_STATE.curr_term = CLIENT_STATE.curr_term+1
            CLIENT_STATE.voted_for = CLIENT_STATE.pid
            CLIENT_STATE.votes[str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.curr_term)]=1
            
            for client in CLIENT_STATE.port_mapping:
                if CLIENT_STATE.active_link[client] == True:
                    req_vote = ReqVote("REQ_VOTE", CLIENT_STATE.pid, CLIENT_STATE.curr_term, CLIENT_STATE.logs[-1].index, CLIENT_STATE.logs[-1].term)
                    print("Requesting Vote for Candidate " + str(CLIENT_STATE.pid) + "|" + " Term: " + str(CLIENT_STATE.curr_term) + " | sent to " + str(client))
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[client]].send(pickle.dumps(req_vote))
                    print("Req Sent")
        except:
            pass
         
                


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
                data = pickle.loads(resp)
                #print("Received data: ", data)
                MessageQueue.append(data)
                #print("A message is received")
            
            except Exception as e:
                print("Exception received: ",e)
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
            #new_client.daemon = True
            new_client.start()

class Persistant_logs(Thread):
    def __init__(self, timeout = 120):
        Thread.__init__(self)
        self.timeout = timeout
        self.curr_time = time.time()
        
    def run(self):
        while(True):
            try: 
                if time.time() - self.curr_time > self.timeout:
                    file = open(CLIENT_STATE.file_path, "wb+")
                    print("SAVING STATE ....")
                    #print("Port Mappings", CLIENT_STATE.port_mapping)
                    pickle.dump(CLIENT_STATE, file, pickle.HIGHEST_PROTOCOL )
                    #CLIENT_STATE_TEMP= pickle.load(file)
                    #print("Port Mapping in Retrieval", CLIENT_STATE_TEMP.port_mapping)
                    file.close()
                    self.curr_time=time.time()
            except Exception as e:
                print(e)
                


class Client:
    def __init__(self, pid, listen_port, port_mapping, file_path):
        self.pid = pid
        self.listen_port = listen_port
        self.port_mapping = port_mapping
        self.file_path = file_path
        self.ip = '127.0.0.1'

    def start_client(self):
        global CLIENT_STATE
        global Dictionaries
        #RECHECK 
        if os.path.exists(self.file_path):
            with open(self.file_path, "rb") as f:
                if(os.stat(self.file_path).st_size!=0):
                    print("LOADING SAVED STATE FROM LOGS")
                    CLIENT_STATE = pickle.loads(f.read()) #what is the type of CLIENT_STATE here
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
                #new_connection.daemon= True
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
            #new_client.daemon = True
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
        persist_thread = Persistant_logs()
        persist_thread.start()
        
        if CLIENT_STATE.curr_state == "LEADER":
            heart_beat_thread = HeartBeat()
            heart_beat_thread.start()
        
        print("Printing Console")
        self.start_console()
        
    
    def start_console(self):
        global CLIENT_STATE
        #global persistCounter
        global Dictionaries
        global state_machine
        global DictionaryDetails
        
        while(True):
            
            '''
             1. create  [<client id>. . .]
             2. put <dictionary id> <key> <value> 
             3. get <dictionary id> <key>
             4. printDict <dictionary id>
             5. printAll
             6. failLink <dest>
             7. fixLink <dest>:
             8. failProcess
            '''
            print("Use the following format to input data: Make sure to communicate with leader")
            print("1. create  [<client id>. . .] // create a dict")
            print("2. put <dictionary id> <key> <value> //Add a key value pair ")
            print("3. get <dictionary id> <key> //get value for the key in dict")
            print("4. printDict <dictionary id> //print clientID+ content ")
            print("5. printAll //print Dictionary IDs of all the dict that client is member of")
            print("6. failLink <dest>")
            print("7. fixLink <dest>")
            print("8. failProcess")
            print("9. fixProcess")
            user_input = input()
            
            #need to handle encryption-decryption
            if user_input.startswith("create"):
                inp_arr= user_input.split()
                client_ids=[]
                for i in range(1,len(inp_arr)):
                    client_ids.append(int(inp_arr[i]))
                
                CLIENT_STATE.persistCounter+=1
                dictId= str(CLIENT_STATE.pid) + "|" + str(CLIENT_STATE.persistCounter)
                print("DICTIONARY ID: ", dictId)
                
                public_key, private_key = rsa.newkeys(256)
                enc_pvt_keys ={}
                
                for client in client_ids:
                    enc_pvt_keys[int(client)] = encryptPvtKey(private_key, CLIENT_STATE.public_keys[int(client)])
                
                client_request = ClientRequest("CLIENT_REQ","CREATE_DICT", dictId, client_ids, key=None, val=None,enc_private_keys=enc_pvt_keys, public_key=public_key)
                #print("ClientRequest")
                #print(client_request)
                self.broadcast(client_request)
                
            
            elif user_input.startswith("put"):
                #put dictionary 
                op, dictId, key, val= user_input.split(" ",3)
                dict_public_key = DictionaryDetails[dictId]
                
                enc_operation = encrypt_content("PUT", dict_public_key)
                enc_key = encrypt_content(key, dict_public_key)
                enc_val = encrypt_content(val, dict_public_key)
                
                client_request = ClientRequest("CLIENT_REQ", enc_operation, dictId, client_ids=None, key=enc_key, val=enc_val, enc_message=None, enc_private_keys=None, public_key=None)
                #print("ClientRequest")
                #print(client_request)
                self.broadcast(client_request)
                
                
                
            elif user_input.startswith("get"):
                op, dictId, key = user_input.split(" ",2)
                dict_public_key = DictionaryDetails[dictId]
                
                enc_operation = encrypt_content("GET", dict_public_key)
                enc_key = encrypt_content(key, dict_public_key)
                
                client_request = ClientRequest("CLIENT_REQ", enc_operation, dictId, client_ids=None, key=enc_key, val=None, enc_message=None, enc_private_keys=None, public_key=None)
                #print("ClientRequest")
                #print(client_request)
                self.broadcast(client_request)
            
            
            elif user_input.startswith("printDict"):
                op, dictId = user_input.split(" ",1)
            
                print("Printing Dictionary for DictId: ", dictId)
                print("---------------------------------------")
                if dictId in Dictionaries:
                    print("Dictionary: ", Dictionaries[dictId])
                    print("--------------------------------------")
                else:
                    print("Dictionary not present: ", dictId)
                    print("---------------------------------------")
            
            elif user_input.startswith("printAll"):
                print("Printing All Dictionaries")
                #print(Dictionaries)
                print("-----------------------------------------")
                for dictId in Dictionaries:
                    dictionary= Dictionaries[dictId]
                    if(CLIENT_STATE.pid in dictionary.clientIds):
                        print(dictionary)
    
            
            elif user_input.startswith("failLink"):
                op, dest = user_input.split(" ",1)
                print("LINK FAILURE BETWEEN " + str(CLIENT_STATE.pid) + "AND " + dest)
                dest = int(dest)
                
                NetworkLinkDest = NetworkLink("FAIL_LINK", CLIENT_STATE.pid)
                #print(CLIENT_STATE.port_mapping)
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(NetworkLinkDest))
                                                            
                CLIENT_STATE.active_link[dest] = False
                
            
            elif user_input.startswith("fixLink"):
                op, dest = user_input.split(" ",1)
                dest = int(dest)
                print("FIX LINK BETWEEN " + str(CLIENT_STATE.pid) + "AND "+ str(dest))
                CLIENT_STATE.active_link[dest] = True
                
                NetworkLinkDest = NetworkLink("FIX_LINK", CLIENT_STATE.pid)
                C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(NetworkLinkDest))
            
            #TODO recheck
            elif user_input.startswith("failProcess"):
                
                Dictionaries = {}
                DictionaryDetails ={}
                
                for dest in CLIENT_STATE.port_mapping:
                    NetworkLinkDest = NetworkLink("FAIL_LINK", CLIENT_STATE.pid)
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(NetworkLinkDest))
                    
                CLIENT_STATE.active_link = {1: False, 2:False, 3:False, 4:False, 5:False}
                CLIENT_STATE.logs=[LogEntry(0,0,None)]
                
                print("Deleting the state machine and the Client State")
                MessageQueue=[]
                sleep()
                #print(CLIENT_STATE.port_mapping)
                del state_machine
                del CLIENT_STATE
                
            #TODO recheck
            elif user_input.startswith("fixProcess"):
                if os.path.exists(self.file_path):
                    with open(self.file_path, "rb") as f:
                        if(os.stat(self.file_path).st_size!=0):
                            print("LOADING SAVED STATE FROM LOGS")
                            CLIENT_STATE= pickle.load(f) #what is the type of CLIENT_STATE here
                            
                            
                            CLIENT_STATE.last_recv_time = time.time()
                            CLIENT_STATE.active_link = {1: True, 2:True, 3:True, 4:True, 5:True}
                            CLIENT_STATE.votes ={}
                            '''
                            for entry in CLIENT_STATE.logs:
                                print(str(entry))
                            '''
                            f.close()
                #print(CLIENT_STATE.port_mapping)
                for dest in CLIENT_STATE.port_mapping:
                    NetworkLinkDest = NetworkLink("FIX_LINK", CLIENT_STATE.pid)
                    C2C_CONNECTIONS[CLIENT_STATE.port_mapping[dest]].send(pickle.dumps(NetworkLinkDest))
                    state_machine = StateMachine()
                    state_machine.start()
                
            else:
                print ("Invalid Input")
            
            

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
                #new_connection.daemon= True
                new_connection.start() # new connection is always ready to receive
            except:
                a=1

    def broadcast(self, append_entry):
        if CLIENT_STATE.curr_state == "LEADER":
            MessageQueue.append(append_entry)
        
        else:
            print("Client Request Received on Follower, moving to Leader")
            #sleep()
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
        timer = Timer(30)
        
    elif sys.argv[1] == "p2":
        listen_port = 7002
        pid=2
        file_path = os.path.join(os.getcwd(),'log/c2.txt')
        port_mapping = {1:7012, 3:7023, 4:7024, 5:7025}
        timer = Timer(35)

    elif sys.argv[1] == "p3":
        listen_port = 7003
        pid=3
        file_path = os.path.join(os.getcwd(),'log/c3.txt')
        port_mapping = {1:7013, 2:7023, 4:7034, 5:7035}
        timer = Timer(40)

    elif sys.argv[1] == "p4":
        listen_port = 7004
        pid=4
        file_path = os.path.join(os.getcwd(),'log/c4.txt')
        port_mapping = {1:7014, 2:7024, 3:7034, 5:7045}
        timer = Timer(45)
    
    elif sys.argv[1] == "p5":
        listen_port = 7005
        pid=5
        file_path = os.path.join(os.getcwd(),'log/c5.txt')
        port_mapping = {1:7015, 2:7025, 3:7035, 4:7045}
        timer = Timer(50)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)


    CLIENT_STATE = ClientState(pid, port_mapping, file_path)
    timer.start()
    

    state_machine = StateMachine()
    state_machine.start()

    

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
    
    


