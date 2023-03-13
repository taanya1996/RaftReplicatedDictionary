import time

class LogEntry:
    def __init__(self, term, index, msg):
        self.term = term
        self.index = index
        self.msg = msg

    def __str__(self):
        return str(self.term) + '|' | str(self.index) + '|' + str(self.msg)

class ReqVote:
    def __init__(self,req_type, candId, term, lastLogIndex, lastLogTerm):
        self.req_type = req_type
        self.candId = candId
        self.term = term
        self.lastLogIndex = lastLogIndex
        self.lastLogTerm = lastLogTerm

class RespVote:
    def __init__(self, req_type, term, voteGranted) -> None:
        self.req_type = req_type
        self.term = term
        self.voteGranted = voteGranted

class AppendEntry:
    def __init__(self, req_type, term, leaderId, prevLogIndex, prevLogTerm, entries, commitIndex):
        self.req_type = req_type
        self.term = term
        self. leaderId = leaderId
        self.prevLogIndex = prevLogIndex
        self.prevLogTerm = prevLogTerm
        self.entries = entries
        self.commitIndex = commitIndex

class ResponseAppendEntry:
    def __init__(self, req_type, pid, term, success):
        self.req_type = req_type
        self.term = term
        self.pid = pid
        self.succeess = success

class ClientState:
    def __init__(self, pid, port_mapping, file_path):
        self.pid = pid
        self. port_mapping = port_mapping
        self.file_path = file_path
        self.curr_leader = 0
        self.curr_term = 0
        self.curr_state = "FOLLOWER"
        self.last_recv_time = time.time()
        self.voted_for = 0
        self.logs = [LogEntry(0,0,None)]
        self.commit_index = 0
        self.active_link = {1: False, 2: False, 3: False, 4: False, 5: False }
        self.votes= {}
        self.leader_heart_beat = time.time()
        self.next_index = {1:0, 2:0, 3:0, 4:0, 5:0}
        self.log_entry_counts={}
        self.public_keys = {}
        self.private_key = None

class ClientMessage:
    def __init__(self, req_type, msg):
        self.req_type = req_type
        self.msg = msg

class ClientRequest:
    def __init__(self, req_type, message_type, sender, group_id, enc_message, enc_private_keys, public_key):
        self.req_type = req_type
        self.message_type = message_type
        self.sender = sender
        self.group_id = group_id
        self.enc_message = enc_message
        self.enc_private_keys = enc_private_keys
        self.public_key = public_key

    def __str__(self):
        if(self.message_type == "WRITE_MESSAGE"):
            return self.message_type + '|' + str(self.group_id) + '| Encrypted Message'
        return self.message_type + '|' + str(self.group_id) + '|' + str(len(self.enc_private_keys))


class NetworkLink:
    def __init__(self, req_type, src, dest):
        self.req_type = req_type
        self.src = src
        self.dest = dest



    

