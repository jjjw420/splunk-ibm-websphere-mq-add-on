'''
IBM Websphere MQ Modular Input for Splunk
Hannes Wagener - 2015 

Used the Splunk provided modular input as example.

DISCLAIMER
You are free to use this code in any way you like, subject to the
Python & IBM disclaimers & copyrights. I make no representations
about the suitability of this software for any purpose. It is
provided "AS-IS" without warranty of any kind, either express or
implied. 

'''

import os
import sys
import logging
import xml.dom.minidom
import xml.sax.saxutils
import time
import threading
import pymqi
import CMQC
#import binascii
#import os
import uuid
#import glob


SPLUNK_HOME = os.environ.get("SPLUNK_HOME")

RESPONSE_HANDLER_INSTANCE = None


# Initialize the root logger with a StreamHandler and a format message:
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')


SCHEME = """<scheme>
    <title>IBM Websphere MQ</title>
    <description>IBM Websphere MQ Modular Input for Splunk</description>
    <use_external_validation>true</use_external_validation>
    <streaming_mode>xml</streaming_mode>
    <use_single_instance>false</use_single_instance>

    <endpoint>
        <args>    
            <arg name="name">
                <title>Input Name</title>
                <description>Name of this input</description>
            </arg>       
            <arg name="queue_manager_name">
                <title>Queue Manager Name</title>
                <description>The Queue Manager name</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>    
            <arg name="queue_manager_host">
                <title>Queue Manager Hostname or IP</title>
                <description>IP or hostname of the queue manager you would like to connect to</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="port">
                <title>Port</title>
                <description>The queue manager listener port. Defaults to 1414</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="server_connection_channel">
                <title>Server Connection Channel</title>
                <description>The server connection channel.  Defaults to SYSTEM.ADMIN.SVRCONN</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
          
            <arg name="queue_names">
                <title>Queue Names</title>
                <description>1 or more Queue Names , comma delimited.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            
            
            <arg name="mqinput_interval">
                <title>Interval</title>
                <description>How often to run the MQ input script. Defaults to 60 seconds.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            
            <arg name="persistent_connection">
                <title>Persistent Connection</title>
                <description>Keep the Queue Manager connection open.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>

            <arg name="use_mq_triggering">
                <title>Use MQ Triggering</title>
                <description>Whether or not to listen for mq trigger messages.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            
            <arg name="start_process_per_queue">
                <title>Start Process Per Queue if more than one queue name is specified.</title>
                <description>Start a process for each queue.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
           
            <arg name="response_handler">
                <title>Response Handler</title>
                <description>Python classname of custom response handler</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="response_handler_args">
                <title>Response Handler Arguments</title>
                <description>Response Handler arguments string ,  key=value,key2=value2</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
        </args>
    </endpoint>
</scheme>
"""


def do_validate():
    
    try:
        config = get_validation_config() 
        
        port = config.get("port")
        mqinput_interval = config.get("mqinput_interval")   
        
        validationFailed = False
    
        if not port is None and int(port) < 1:
            print_validation_error("Port value must be a positive integer")
            validationFailed = True
        if not mqinput_interval is None and int(mqinput_interval) < 1:
            print_validation_error("Script polling interval must be a positive integer")
            validationFailed = True
        if validationFailed:
            sys.exit(2)
               
    except: # catch *all* exceptions
        e = sys.exc_info()[1]
        logging.error("Exception getting XML configuration: %s" % str(e))
        sys.exit(1)
        raise   
    
def do_run():
    
    logging.debug("... MQINPUT: do_run() ...") 
    
    config = get_input_config() 
 
    queue_manager_name = config.get("queue_manager_name")
    queue_manager_host = config.get("queue_manager_host")
    port = int(config.get("port",1414))
    server_connection_channel = config.get("server_connection_channel","SYSTEM.ADMIN,SVRCON")
    
    queue_names = config.get("queue_names")
    
    if not queue_names is None:
        queue_name_list = map(str,queue_names.split(","))   
        #trim any whitespace using a list comprehension
        queue_name_list = [x.strip(' ') for x in queue_name_list]
    
    splunk_host = config.get("host")    
    name =  config.get("name")
    
    mqinput_interval = int(config.get("mqinput_interval",60))   
    use_mq_triggering = int(config.get("use_mq_triggering",0))
    persistent_connection = int(config.get("persistent_connection",0))
    #include_mqmd = int(config.get("include_mqmd",0))
  
    #use_mqmd_puttime = int(config.get("use_mqmd_puttime",0))
    start_process_per_queue = int(config.get("start_process_per_queue",0))
    
    response_handler_args = {} 
    response_handler_args_str = config.get("response_handler_args")
    if not response_handler_args_str is None:
        response_handler_args = dict((k.strip(), v.strip()) for k,v in 
              (item.split('=') for item in response_handler_args_str.split(',')))
        
    response_handler=config.get("response_handler","DefaultResponseHandler")
    logging.debug("Using response_handler:" + response_handler)
    module = __import__("responsehandlers")
    class_ = getattr(module,response_handler)

    global RESPONSE_HANDLER_INSTANCE
    RESPONSE_HANDLER_INSTANCE = class_(**response_handler_args)

    try: 
        # update all the root StreamHandlers with a new formatter that includes the config information
        for h in logging.root.handlers:
            if isinstance(h, logging.StreamHandler):
                h.setFormatter( logging.Formatter('%(levelname)s %(message)s mqinput_stanza:{0}'.format(name)) )

    except: # catch *all* exceptions
        e = sys.exc_info()[1]
        logging.error("Could not update logging templates: %s host:'" % str(e)) 
    
    
    if use_mq_triggering:
        pass
#         trapThread = TrapThread(trap_port,trap_host,ipv6)
#         trapThread.start()
#         if snmp_version == "3":
#             trapThread = V3TrapThread(trap_port,trap_host,ipv6,v3_securityName,v3_authKey,v3_authProtocol,v3_privKey,v3_privProtocol)
#             trapThread.start()  

    #splunk_host = "host"    
    if not (queue_names is None) and not(queue_manager_host is None) and not(port is None) and not(server_connection_channel is None): 
        
        group_id = str(uuid.uuid4())
        pid_fle = open("/tmp/%s_current.pid" % name.replace("://", "-"), "w")
        logging.debug("Starting new thread group. " + group_id)
        pid_fle.write(group_id)
        pid_fle.close()
        #persistent_connection = False
        if start_process_per_queue:  
            logging.debug("Starting process per queue")
            qps = []            
            for queue_name in queue_name_list:
                qps.append(QueuePollerThread(group_id, name, splunk_host, queue_manager_name, queue_manager_host, port, server_connection_channel, queue_name, mqinput_interval, start_process_per_queue, persistent_connection)) 
                qps[-1].start()
        else:
            logging.debug("Starting single process")
            qp = QueuePollerThread(group_id, name, splunk_host, queue_manager_name, queue_manager_host, port,server_connection_channel, queue_names, mqinput_interval, start_process_per_queue, persistent_connection) 
            qp.start() 

# def make_mqmd(self, msg_desc, pretty_mqmd):
#     
#     mqmd_dict = {}
#     
#     if pretty_mqmd and MQMD_DICTS["mqmd"].has_key(msg_desc['StrucId']):
#         mqmd_dict['StrucId'] =  MQMD_DICTS["mqmd"][msg_desc['StrucId']]
#     else:
#         mqmd_dict['StrucId'] = msg_desc['StrucId']
#     
#     if pretty_mqmd and MQMD_DICTS["mqmd"].has_key(msg_desc['Version']):
#         mqmd_dict['Version'] =  MQMD_DICTS["mqmd"][msg_desc['Version']]
#     else:    
#         mqmd_dict['Version'] = msg_desc['Version']
#     
#     if pretty_mqmd and MQMD_DICTS["mqro"].has_key(msg_desc['Report']):
#         mqmd_dict['Report'] =  MQMD_DICTS["mqro"][msg_desc['Report']]
#     else:
#         mqmd_dict['Report'] = msg_desc['Report']
#         
#     if pretty_mqmd and MQMD_DICTS["mqmt"].has_key(msg_desc['MsgType']):
#         mqmd_dict['MsgType'] =  MQMD_DICTS["mqmt"][msg_desc['MsgType']]
#     else:
#         mqmd_dict['MsgType'] = msg_desc['MsgType']
#     
#     if pretty_mqmd and MQMD_DICTS["mqei"].has_key(msg_desc['Expiry']):
#         mqmd_dict['Expiry'] =  MQMD_DICTS["mqei"][msg_desc['Expiry']]
#     else:
#         mqmd_dict['Expiry'] = msg_desc['Expiry']
#     
#     if pretty_mqmd and MQMD_DICTS["mqfb"].has_key(msg_desc['Feedback']):
#         mqmd_dict['Feedback'] =  MQMD_DICTS["mqfb"][msg_desc['Feedback']]
#     else:
#             mqmd_dict['Feedback'] = msg_desc['Feedback']
# 
#     if pretty_mqmd and MQMD_DICTS["mqenc"].has_key(msg_desc['Encoding']):
#         mqmd_dict['Encoding'] =  MQMD_DICTS["mqenc"][msg_desc['Encoding']]
#     else:
#         mqmd_dict['Encoding'] = msg_desc['Encoding']
#     
#     if pretty_mqmd and MQMD_DICTS["mqccsi"].has_key(msg_desc['CodedCharSetId']):
#         mqmd_dict['CodedCharSetId'] =  MQMD_DICTS["mqccsi"][msg_desc['CodedCharSetId']]
#     else:
#         mqmd_dict['CodedCharSetId'] = msg_desc['CodedCharSetId']
#     
#     if pretty_mqmd and MQMD_DICTS["mqfmt"].has_key(msg_desc['Format']):
#         mqmd_dict['Format'] =  MQMD_DICTS["mqfmt"][msg_desc['Format']]
#     else:
#         mqmd_dict['Format'] = msg_desc['Format']
#     
#     if pretty_mqmd and MQMD_DICTS["mqpri"].has_key(msg_desc['Priority']):
#         mqmd_dict['Priority'] =  MQMD_DICTS["mqpri"][msg_desc['Priority']]
#     else:
#         mqmd_dict['Priority'] = msg_desc['Priority']
#         
#     if pretty_mqmd and MQMD_DICTS["mqper"].has_key(msg_desc['Persistence']):
#         mqmd_dict['Persistence'] =  MQMD_DICTS["mqper"][msg_desc['Persistence']]
#     else:
#         mqmd_dict['Persistence'] = msg_desc['Persistence']
#         
#     if pretty_mqmd and MQMD_DICTS["mqat"].has_key(msg_desc['PutApplType']):
#         mqmd_dict['PutApplType'] =  MQMD_DICTS["mqat"][msg_desc['PutApplType']]
#     else:
#         mqmd_dict['PutApplType'] = msg_desc['PutApplType']
#         
#     if pretty_mqmd and MQMD_DICTS["mqmf"].has_key(msg_desc['MsgFlags']):
#         mqmd_dict['MsgFlags'] =  MQMD_DICTS["mqmf"][msg_desc['MsgFlags']]
#     else:
#         mqmd_dict['MsgFlags'] = msg_desc['MsgFlags']
# 
#     if pretty_mqmd and MQMD_DICTS["mqol"].has_key(msg_desc['OriginalLength']):
#         mqmd_dict['OriginalLength'] =  MQMD_DICTS["mqol"][msg_desc['OriginalLength']]
#     else:
#         mqmd_dict['OriginalLength'] = msg_desc['OriginalLength']
#         
#     mqmd_dict['MsgId'] = binascii.hexlify(msg_desc['MsgId'])
#     mqmd_dict['CorrelId'] = binascii.hexlify(msg_desc['CorrelId'])
#     mqmd_dict['BackoutCount'] = msg_desc['BackoutCount']
#     mqmd_dict['ReplyToQ'] = msg_desc['ReplyToQ']
#     mqmd_dict['ReplyToQMgr'] = msg_desc['ReplyToQMgr']
#     mqmd_dict['UserIdentifier'] = binascii.hexlify(msg_desc['UserIdentifier'])
#     mqmd_dict['AccountingToken'] = binascii.hexlify(msg_desc['AccountingToken'])
#     mqmd_dict['ApplIdentityData'] = binascii.hexlify(msg_desc['ApplIdentityData'])
#     mqmd_dict['PutApplName'] = binascii.hexlify(msg_desc['PutApplName'])
#     mqmd_dict['PutDate'] = msg_desc['PutDate']
#     mqmd_dict['PutTime'] = msg_desc['PutTime']
#     mqmd_dict['ApplOriginData'] = (msg_desc['ApplOriginData'])
#     mqmd_dict['GroupId'] = binascii.hexlify(msg_desc['GroupId'])
#     mqmd_dict['MsgSeqNumber'] = msg_desc['MsgSeqNumber']
#     mqmd_dict['Offset'] = msg_desc['Offset']
# 
#     return mqmd_dict

class QueuePollerThread(threading.Thread):
    
    def __init__(self, group_id, name, splunk_host, queue_manager_name, queue_manager_host, port,server_connection_channel, queue_names, mqinput_interval, start_process_per_queue, persistent_connection, **kw):
        threading.Thread.__init__(self)
        #logging.debug("-------------------------------------------------------")
        logging.debug("Started Queue Poller for queue/s: " + queue_names + " Thread Group:" + group_id)
        
        self.config_name = name
        self.queue_manager_name = queue_manager_name
        self.queue_manager_host = queue_manager_host
        self.port = port
        self.server_connection_channel = server_connection_channel
        self.queue_names = queue_names
        self.mqinput_interval = mqinput_interval
        self.start_process_per_queue = start_process_per_queue
        self._qm = None
        
        self.setName(group_id)
        #logging.debug("****** Started NEW THREAD: " + self.getName())
        self.splunk_host = splunk_host
        
        self.queue_name_list = map(str, self.queue_names.split(","))   
        #trim any whitespace using a list comprehension
        #logging.debug("before queue name list")
        self.queue_name_list = [x.strip(' ') for x in self.queue_name_list]
        #logging.debug("after queue name lust")
        self.socket = "%s(%i)" % (str(self.queue_manager_host).strip(), self.port)
        #logging.debug("after self.socket %s" % self.socket)
        self.kw = kw
        self.persistent_connection = persistent_connection
    
    def run(self):
         
        #logging.debug("in run") 
        
        while True:
            try:
                
                #logging.debug("before connect %s %s %s" % (self.queue_manager_name, self.server_connection_channel, self.socket))
                file_pid = str(open("/tmp/%s_current.pid" % self.config_name.replace("://", "-"), "r").read())
                #logging.debug("%%%%%% this pid:" + str(self.getName()) + " File pid:" + str(file_pid))    
                if self.getName().strip() != file_pid.strip():
                    #logging.debug("$$$$ Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                    done = True
                    sys.exit(1)
                else:
                    pass
                    #logging.debug("!!! NOT Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                
                if self._qm is None:
                    self._qm = pymqi.QueueManager(None)
                    logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                   
                    self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket)
                    logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                else:
                    if not self.persistent_connection: 
                        self._qm = pymqi.QueueManager(None)
                        logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                       
                        self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket)
                        logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                    else:
                        if not self._qm._is_connected():
                            self._qm = pymqi.QueueManager(None)
                            logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                            
                            self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket)
                            logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                            
                queues = []
                logging.debug("Queue name list: %s" % str(self.queue_name_list))
                
                for queue_name in self.queue_name_list:
                    try:
                        queues.append((queue_name, pymqi.Queue(self._qm, queue_name, CMQC.MQOO_INPUT_SHARED)))
                        #logging.debug("queue loop.  queue name:" + str(queue_name))
                    except Exception, ex:
                        logging.error("Unable to open queue:" + str(queue_name) + " Exception: " + str(ex))
                    
                get_opts = pymqi.gmo(Options = CMQC.MQGMO_FAIL_IF_QUIESCING)
                
                #logging.debug("after get_opts") 
                msg_desc = pymqi.md()
                #logging.debug("Start get")
                for (queue_name, queue_obj) in queues:
                    #logging.debug("queue = %s " % queue_name)
                    #logging.debug("Current tid:" + str(self.getName()) + " queue:" + queue_name)
                    #logging.debug("Check pid: queue:" + queue_name)
          
                    file_pid = str(open("/tmp/%s_current.pid" % self.config_name.replace("://", "-"), "r").read())
                    #logging.debug("%%%%%% this pid:" + str(self.getName()) + " File pid:" + str(file_pid))    
                    if self.getName().strip() != file_pid.strip():
                        #open("/opt/esb/stop.txt", "a").write("$$$$ Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                        #logging.debug("$$$$ Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                        done = True
                        sys.exit(1)
                    else:
                        pass
                        #logging.debug("!!! NOT Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                    
                    done = False
                    while not done:
                       
                        try:
                          
                            logging.debug("Before MQGET")
                            msg_desc['MsgId'] = ''
                            msg_desc['CorrelId'] = '' 
                            msg_data = queue_obj.get(None, msg_desc, get_opts)   
                            logging.debug("Got message. ")# MQMD:" + str(msg_desc.get()) + "MSG:" + msg_data)
                            
                            handle_output(self.splunk_host, self.queue_manager_name, queue_name, msg_data, msg_desc, False,  **self.kw)  
                            logging.debug("Handled output")
                        except pymqi.MQMIError, e:
                            if e.reason == 2033:
                                logging.debug("Done! 2033. No more messages!")
                                done = True
                            else:
                                logging.error("MQ Exception occurred: %s " % (str(e)))
                                done = True
                    
                    queue_obj.close()
                               
                if not self.persistent_connection:    
                    self._qm.disconnect()
            except pymqi.MQMIError, e:
                if e.reason == 2033:
                    pass
                else:
                    logging.error("MQ Exception occurred: %s " % (str(e)))  
                    if self._qm is not None:
                        if not self.persistent_connection and self._qm._is_connected():
                            self._qm.disconnect()
                    
            except: # catch *all* exceptions
                e = sys.exc_info()[1]
                logging.error("Stopping.  Exception occurred in QueuePoller: %s" % str(e))
                sys.exit(1)
         
            time.sleep(float(self.mqinput_interval))
                 
class MQTriggerThread(threading.Thread):
     
    def __init__(self, queue_manager_name, queue_manager_host, port,server_connection_channel, queue_names, mqinput_interval, **kw):
        threading.Thread.__init__(self)
        self.queue_manager_name = queue_manager_name
        self.queue_manager_host = queue_manager_host
        self.port = port
        self.server_connection_channel = server_connection_channel
        self.queue_names = queue_names
        self.queue_name_list = map(str,queue_names.split(","))   
        #trim any whitespace using a list comprehension
        self.queue_name_list = [x.strip(' ') for x in self.queue_name_list]
        
        self.socket = "%s(%d)" % (str(self.queue_manager_host).strip(), self.port)
        self.kw = kw
     
    def run(self):
        pass
#         try:     
#             transportDispatcher.registerTransport(domainName, transport.openServerMode((self.host, self.port)))
#        
#             transportDispatcher.jobStarted(1)
#             # Dispatcher will never finish as job#1 never reaches zero
#             transportDispatcher.runDispatcher()     
#         except: # catch *all* exceptions
#             e = sys.exc_info()[1]
#             transportDispatcher.closeDispatcher()
#             logging.error("Failed to register transport and run dispatcher: %s" % str(e))
#             sys.exit(1)


            
# prints validation error data to be consumed by Splunk
def print_validation_error(s):
    print "<error><message>%s</message></error>" % xml.sax.saxutils.escape(s)

def handle_output(splunk_host, queue_manager_name, queue, msg_desc, msg_data, from_trigger, **kw): 
    
    try:
        RESPONSE_HANDLER_INSTANCE(splunk_host, queue_manager_name, queue, msg_desc, msg_data, from_trigger,  **kw)
        sys.stdout.flush()               
    except:
        e = sys.exc_info()[1]
        logging.error("Exception occurred while handling response output: %s" % str(e))
    
def usage():
    print "usage: %s [--scheme|--validate-arguments]"
    logging.error("Incorrect Program Usage")
    sys.exit(2)

def do_scheme():
    logging.debug("MQINPUT: DO scheme..")  
    print SCHEME

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_input_config():
    config = {}

    try:
        # read everything from stdin
        config_str = sys.stdin.read()

        # parse the config XML
        doc = xml.dom.minidom.parseString(config_str)
        root = doc.documentElement
        conf_node = root.getElementsByTagName("configuration")[0]
        if conf_node:
            logging.debug("XML: found configuration")
            stanza = conf_node.getElementsByTagName("stanza")[0]
            if stanza:
                stanza_name = stanza.getAttribute("name")
                if stanza_name:
                    logging.debug("XML: found stanza " + stanza_name)
                    config["name"] = stanza_name

                    params = stanza.getElementsByTagName("param")
                    for param in params:
                        param_name = param.getAttribute("name")
                        logging.debug("XML: found param '%s'" % param_name)
                        if param_name and param.firstChild and \
                           param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                            data = param.firstChild.data
                            config[param_name] = data
                            logging.debug("XML: '%s' -> '%s'" % (param_name, data))

        checkpnt_node = root.getElementsByTagName("checkpoint_dir")[0]
        if checkpnt_node and checkpnt_node.firstChild and \
           checkpnt_node.firstChild.nodeType == checkpnt_node.firstChild.TEXT_NODE:
            config["checkpoint_dir"] = checkpnt_node.firstChild.data

        if not config:
            raise Exception, "Invalid configuration received from Splunk."

        
    except: # catch *all* exceptions
        e = sys.exc_info()[1]
        raise Exception, "Error getting Splunk configuration via STDIN: %s" % str(e)

    return config

#read XML configuration passed from splunkd, need to refactor to support single instance mode
def get_validation_config():
    val_data = {}

    # read everything from stdin
    val_str = sys.stdin.read()

    # parse the validation XML
    doc = xml.dom.minidom.parseString(val_str)
    root = doc.documentElement

    logging.debug("XML: found items")
    item_node = root.getElementsByTagName("item")[0]
    if item_node:
        logging.debug("XML: found item")

        name = item_node.getAttribute("name")
        val_data["stanza"] = name

        params_node = item_node.getElementsByTagName("param")
        for param in params_node:
            name = param.getAttribute("name")
            logging.debug("Found param %s" % name)
            if name and param.firstChild and \
               param.firstChild.nodeType == param.firstChild.TEXT_NODE:
                val_data[name] = param.firstChild.data

    return val_data

if __name__ == '__main__':
      
    if len(sys.argv) > 1:
        if sys.argv[1] == "--scheme":           
            do_scheme()
        elif sys.argv[1] == "--validate-arguments":
            do_validate()
        else:
            usage()
    else:
        do_run()
        
    sys.exit(0)
