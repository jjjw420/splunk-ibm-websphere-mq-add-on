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
from pymqi import CMQC as CMQC
#import binascii
#import os
import uuid
#import glob


SPLUNK_HOME = os.environ.get("SPLUNK_HOME")

RESPONSE_HANDLER_INSTANCE = None


# Initialize the root logger with a StreamHandler and a format message:
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')


SCHEME = """<scheme>
    <title>IBM Websphere MQ Channel Status</title>
    <description>IBM Websphere MQ Channel Status Input for Splunk.</description>
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
          
            <arg name="channel_names">
                <title>Channel Names</title>
                <description>One or more Channel Names. Comma delimited. Use "ALL" to query all available channels.  Only "server connection, "sender" and "cluster sender" channel status will be checked.</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            
            
            <arg name="mqchs_interval">
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
            
            <arg name="response_handler">
                <title>Response Handler</title>
                <description>Python classname of custom response handler</description>
                <required_on_edit>false</required_on_edit>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="response_handler_args">
                <title>Response Handler Arguments</title>
                <description>Response Handler arguments string, key=value,key2=value2. include_zero_values=true/false - Include values that are set to zero or default values in the event.</description>
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
        mqchs_interval = config.get("mqchs_interval")   
        
        validationFailed = False
    
        if not port is None and int(port) < 1:
            print_validation_error("Port value must be a positive integer")
            validationFailed = True
        if not mqchs_interval is None and int(mqchs_interval) < 1:
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
    
    logging.debug("... MQCHS: do_run() ...") 
    
    config = get_input_config() 
 
    queue_manager_name = config.get("queue_manager_name")
    queue_manager_host = config.get("queue_manager_host")
    port = int(config.get("port",1414))
    server_connection_channel = config.get("server_connection_channel","SYSTEM.ADMIN,SVRCON")
    
    channel_names = config.get("channel_names")
    
    if channel_names is not None:
        channel_name_list = map(str,channel_names.split(","))   
        #trim any whitespace using a list comprehension
        channel_name_list = [x.strip(' ') for x in channel_name_list]
    
    splunk_host = config.get("host")    
    name =  config.get("name")
    
    mqchs_interval = int(config.get("mqinput_interval",60))   
    persistent_connection = int(config.get("persistent_connection",0))
    create_event_per_channnel = int(config.get("create_event_per_channnel",0))
    include_zero_values = int(config.get("include_zero_values",0))
    
    response_handler_args = {} 
    response_handler_args_str = config.get("response_handler_args")
    if not response_handler_args_str is None:
        response_handler_args = dict((k.strip(), v.strip()) for k,v in 
              (item.split('=') for item in response_handler_args_str.split(',')))
        
    response_handler=config.get("response_handler","DefaultChannelStatusResponseHandler")
    logging.debug("Using response_handler:" + response_handler)
    module = __import__("responsehandlers")
    class_ = getattr(module,response_handler)

    global RESPONSE_HANDLER_INSTANCE
    RESPONSE_HANDLER_INSTANCE = class_(**response_handler_args)
    
    try: 
        # update all the root StreamHandlers with a new formatter that includes the config information
        for h in logging.root.handlers:
            if isinstance(h, logging.StreamHandler):
                h.setFormatter( logging.Formatter('%(levelname)s %(message)s mqchs_stanza:{0}'.format(name)) )

    except: # catch *all* exceptions
        e = sys.exc_info()[1]
        logging.error("Could not update logging templates: %s host:'" % str(e)) 
    
    if not (channel_names is None) and not(queue_manager_host is None) and not(port is None) and not(server_connection_channel is None): 
        
        group_id = str(uuid.uuid4())
        pid_fle = open("/tmp/%s_current.pid" % name.replace("://", "-"), "w")
        logging.debug("Starting new thread group. " + group_id)
        pid_fle.write(group_id)
        pid_fle.close()
        logging.debug("Starting single process")
        qp = ChannelStatusPollerThread(group_id, name, splunk_host, queue_manager_name, queue_manager_host, port,server_connection_channel, channel_names, mqchs_interval, persistent_connection, create_event_per_channnel, include_zero_values) 
        qp.start() 


class ChannelStatusPollerThread(threading.Thread):
    
    def __init__(self, group_id, name, splunk_host, queue_manager_name, queue_manager_host, port,server_connection_channel, channel_names, mqchs_interval, persistent_connection, create_event_per_channnel, include_zero_values, **kw):
        threading.Thread.__init__(self)
        #logging.debug("-------------------------------------------------------")
        logging.debug("Started channel Poller for channel/s: " + channel_names + " Thread Group:" + group_id)
        
        self.config_name = name
        self.queue_manager_name = queue_manager_name
        self.queue_manager_host = queue_manager_host
        self.port = port
        self.server_connection_channel = server_connection_channel
        self.channel_names = channel_names
        self.mqinput_interval = mqchs_interval
        self._qm = None
        
        self.setName(group_id)
        self.splunk_host = splunk_host
        
        self.channel_name_list = map(str, self.channel_names.split(","))   
        self.channel_name_list = [x.strip(' ') for x in self.channel_name_list]
        self.socket = "%s(%i)" % (str(self.queue_manager_host).strip(), self.port)
        self.kw = kw
        self.persistent_connection = persistent_connection
        self.create_event_per_channnel = create_event_per_channnel
        self.include_zero_values = include_zero_values
      
    def run(self):
        
        
        done = False 
        while not done:
            try:            
                #logging.debug("before connect %s %s %s" % (self.queue_manager_name, self.server_connection_channel, self.socket))
                file_pid = str(open("/tmp/%s_current.pid" % self.config_name.replace("://", "-"), "r").read())
                #logging.debug("%%%%%% this pid:" + str(self.getName()) + " File pid:" + str(file_pid))    
                if self.getName().strip() != file_pid.strip():
                    # another thrread has started and this one is not done.   stop..
                    #logging.debug("$$$$ Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                    done = True
                    sys.exit(1)
                else:
                    pass
                    #logging.debug("!!! NOT Stopping... this pid:" + str(self.getName()) + " File pid:" + str(file_pid))
                
                if self._qm is None:
                    self._qm = pymqi.QueueManager(None)
                    logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                   
                    self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket, None, None)
                    logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                else:
                    if not self.persistent_connection: 
                        self._qm = pymqi.QueueManager(None)
                        logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                       
                        self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket, None, None)
                        logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                    else:
                        if not self._qm._is_connected():
                            self._qm = pymqi.QueueManager(None)
                            logging.debug("Connecting to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                            
                            self._qm.connectTCPClient(self.queue_manager_name, pymqi.cd(), str(self.server_connection_channel), self.socket, None, None)
                            logging.debug("Successfully Connected to " + str(self.queue_manager_name) + str(self.server_connection_channel))
                            
                logging.debug("channel name list: %s" % str(self.channel_name_list))
                
                pcf = pymqi.PCFExecute(self._qm)
                #logging.debug("Start get")
                for channel_name in self.channel_name_list:
                    """
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
                    """
                    
                    get_chs_args = {pymqi.CMQCFC.MQCACH_CHANNEL_NAME: channel_name}
                    
                    try:
                        pcf_response = pcf.MQCMD_INQUIRE_CHANNEL_STATUS(get_chs_args)
                        
                    except pymqi.MQMIError, e:
                        if e.comp == pymqi.CMQC.MQCC_FAILED and e.reason == pymqi.CMQC.MQRC_UNKNOWN_OBJECT_NAME:
                            logging.info("Channel '%s' does not exist." % channel_name)
                        else:
                            if e.comp == pymqi.CMQC.MQCC_FAILED and e.reason == pymqi.CMQCFC.MQRCCF_CHL_STATUS_NOT_FOUND:
                                logging.debug("No status for channel '%s'." % channel_name)
                            raise
                    else:
                        handle_output(self.splunk_host, self.queue_manager_name, channel_name, pcf_response,  **self.kw)  
                    
                if not self.persistent_connection:    
                    self._qm.disconnect()
            except pymqi.MQMIError, e:
                logging.error("MQ Exception occurred: %s " % (str(e)))  
                if self._qm is not None:
                    if not self.persistent_connection and self._qm._is_connected():
                        self._qm.disconnect()
                
            except: # catch *all* exceptions
                e = sys.exc_info()[1]
                logging.error("Stopping.  Exception occurred in ChannelStatusPoller: %s" % str(e))
                sys.exit(1)
         
            time.sleep(float(self.mqinput_interval))
        
# prints validation error data to be consumed by Splunk
def print_validation_error(s):
    print "<error><message>%s</message></error>" % xml.sax.saxutils.escape(s)

def handle_output(splunk_host, queue_manager_name, channel_name, pcf_response, **kw): 
    
    try:
        RESPONSE_HANDLER_INSTANCE(splunk_host, queue_manager_name, channel_name, pcf_response, **kw)
        sys.stdout.flush()               
    except:
        e = sys.exc_info()[1]
        logging.error("Exception occurred while handling response output: %s" % str(e))
    
def usage():
    print "usage: %s [--scheme|--validate-arguments]"
    logging.error("Incorrect Program Usage")
    sys.exit(2)

def do_scheme():
    logging.debug("MQCHS: DO scheme..")  
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
