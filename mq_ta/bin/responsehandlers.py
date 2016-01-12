#add your custom response handler class to this module
import json
import datetime
import time
import binascii
import base64
import pymqi
import CMQC
import string
import os
import lxml
import logging
import gzip
import re

""""
The DefaultResponseHandler uses the "syslog" or "generic single line" source types and supports the following options:

payload_limit=<number of bytes>.  Only include the first x number of bytes of the payload in the event.  Default = 1024 (1kb)
include_mqmd=<true/false>  If true the MQMD of the message will be included in the splunk event.
pretty_mqmd=<true/false>  If true the MQMD of the message will be beautified by looking up the textual descriptions for the values in ther MQMD.
use_mqmd_puttime=<true/false>  If true the MQMD PutDate and PutTime will be combined and used as the time for the Splunk event
encode_payload=<false/base64/hexBinary> If false the payload will be included as-is(this can have negative effects if the payload contains non-text data)
                                        If base64 the whole payload will be base64 encoded.
                                        if hexBinary the whole payload will be converted to the hexadecimal representation of the payload.

"""
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')

class DefaultResponseHandler:
    
    
    def __init__(self,**args):
        self.args = args
        self.mqmd_dicts = None
        
        if self.args.has_key("include_mqmd"):
            if self.args["include_mqmd"].lower().strip() == "true":
                self.include_mqmd = True
            else:
                self.include_mqmd = False
        else:
            self.include_mqmd = False
        
                
        if self.args.has_key("pretty_mqmd"):
            if self.args["pretty_mqmd"].strip().lower() == "true":
                self.pretty_mqmd = True
 
                mqmd_dict = pymqi._MQConst2String(CMQC, "MQMD_")
                mqro_dict = pymqi._MQConst2String(CMQC, "MQRO_")
                mqmt_dict = pymqi._MQConst2String(CMQC, "MQMT_")
                mqei_dict = pymqi._MQConst2String(CMQC, "MQEI_")
                mqfb_dict = pymqi._MQConst2String(CMQC, "MQFB_")
                mqenc_dict = pymqi._MQConst2String(CMQC, "MQENC_")
                mqccsi_dict = pymqi._MQConst2String(CMQC, "MQCCSI_")
                mqfmt_dict = pymqi._MQConst2String(CMQC, "MQFMT_")
                mqpri_dict = pymqi._MQConst2String(CMQC, "MQPRI_")
                mqper_dict = pymqi._MQConst2String(CMQC, "MQPER_")
                mqat_dict = pymqi._MQConst2String(CMQC, "MQAT_")
                mqmf_dict = pymqi._MQConst2String(CMQC, "MQMF_")
                mqol_dict = pymqi._MQConst2String(CMQC, "MQOL_")
        
                self.mqmd_dicts = {"mqmd": mqmd_dict, "mqro": mqro_dict, "mqmt": mqmt_dict, "mqei": mqei_dict, "mqfb": mqfb_dict, "mqenc": mqenc_dict, "mqccsi": mqccsi_dict,"mqfmt": mqfmt_dict, "mqpri": mqpri_dict, "mqper": mqper_dict, "mqat": mqat_dict, "mqmf": mqmf_dict, "mqol": mqol_dict}
 
            else:
                self.pretty_mqmd = False
        else:
            self.pretty_mqmd = False
            
        if self.args.has_key("use_mqmd_puttime"):
            if self.args["use_mqmd_puttime"].lower().strip() == "true":
                self.use_mqmd_puttime = True
            else:
                self.use_mqmd_puttime = False
        else:
            self.use_mqmd_puttime = False

        if self.args.has_key("payload_limit"):
            try:
                self.payload_limit = int(self.args["payload_limit"].strip())
            except:
                self.payload_limit = 1024
        else:
            self.payload_limit = 1024 
        
        if self.args.has_key("encode_payload"):
            self.encode_payload = self.args["encode_payload"].lower().strip()
        else:
            self.encode_payload = "false" 
            
        if self.args.has_key("make_mqmd_printable"):
            self.make_mqmd_printable = self.args["make_mqmd_printable"].lower().strip()
        else:
            self.make_mqmd_printable = False
            
        if self.args.has_key("make_payload_printable"):
            self.make_payload_printable = self.args["make_payload_printable"].lower().strip()
        else:
            self.make_payload_printable = False 
            
        
        
    def __call__(self, splunk_host, queue_manager_name, queue, msg_data, msg_desc, from_trigger, **kw):        
        
        splunk_event =""
        
        mqmd_str = ""
        if self.include_mqmd and (msg_desc is not None):
            new_mqmd = make_mqmd(msg_desc, self.mqmd_dicts, self.pretty_mqmd, self.make_mqmd_printable)
            for (mqmd_key, mqmd_value) in new_mqmd.items():
                if isinstance(mqmd_value, int) or isinstance(mqmd_value, float) or str(mqmd_value).startswith("MQ"):
                    mqmd_str = mqmd_str + " %s=%s" % (str(mqmd_key).strip(), str(mqmd_value))
                else:
                    mqmd_str = mqmd_str + ' %s="%s"' % (str(mqmd_key).strip(), str(mqmd_value))
        
        index_time = "[" + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + time.strftime("%z") + "]"   
        if self.use_mqmd_puttime:
            puttime = datetime.datetime.strptime(msg_desc["PutDate"] + " " + msg_desc["PutTime"][0:6], "%Y%m%d %H%M%S")
            #puttime = puttime.replace(tzinfo=pytz.timezone("GMT"))
            localtime = puttime - datetime.timedelta(seconds=time.timezone)

            h_secs = msg_desc["PutTime"][6:]
            index_time = "[" + localtime.strftime("%Y-%m-%d %H:%M:%S") + "." + h_secs + "0 " +  time.strftime("%z") + "]"
            

        
        payload = ""
        
        if self.encode_payload == "base64":
            payload = ' payload="%s"' % str(base64.encodestring(msg_data[:self.payload_limit])) 
        else:
            if self.encode_payload == "hexbinary":
                payload = ' payload="%s"' % str(binascii.hexlify(msg_data[:self.payload_limit])) 
            else:
                if self.make_payload_printable:
                    payload = ' payload="%s"' % make_printable(msg_data[:self.payload_limit])
                else:
                    payload = ' payload="%s"' % msg_data[:self.payload_limit]
        
        queue_manager_name_str = " queue_manager=%s" % queue_manager_name
        queue = " queue=%s" % queue 
        host = " " + splunk_host
        process = " mqinput(%i):" % os.getpid() 
        
        #handle trigger
        if from_trigger:
            pass
        else:  
            splunk_event = splunk_event + index_time + host + process + queue_manager_name_str +  queue + mqmd_str + payload
            print_xml_single_instance_mode(splunk_host, splunk_event)
        
        
class JSONFormatterResponseHandler:
    
    def __init__(self,**args):
        pass
        
    def __call__(self, response_object,destination,table=False,from_trap=False,trap_metadata=None,split_bulk_output=False,mibView=None):        
        #handle tables         
        if table:
            values = []
            for varBindTableRow in response_object:
                row = {}
                for name, val in varBindTableRow:                              
                    row[name.prettyPrint()] = val.prettyPrint()
                values.append(row)
            print_xml_single_instance_mode(destination, json.dumps(values))            
        #handle scalars
        else: 
            values = {} 
            for name, val in response_object:
                values[name.prettyPrint()] = val.prettyPrint()
            print_xml_single_instance_mode(destination, json.dumps(values))      
 


def is_printable(char):
    '''Return true if the character char is printable or false if it is not printable.
    '''
    if string.printable.count(char) > 0:
        return True
    else:
        return False

def make_printable(instr):
    '''Return a printable representation of the string instr.
    '''
    retstr = ''
    for char in instr:
        if not is_printable(char):
            retstr = retstr + '.'
        else:
            retstr = retstr + char
    return retstr
              
def make_mqmd(msg_desc, mqmd_dicts, pretty_mqmd, make_mqmd_printable):
    
    mqmd_dict = {}
    
    if pretty_mqmd and mqmd_dicts["mqmd"].has_key(msg_desc['StrucId']):
        mqmd_dict['StrucId'] =  mqmd_dicts["mqmd"][msg_desc['StrucId']]
    else:
        mqmd_dict['StrucId'] = msg_desc['StrucId']
    
    if pretty_mqmd and mqmd_dicts["mqmd"].has_key(msg_desc['Version']):
        mqmd_dict['Version'] =  mqmd_dicts["mqmd"][msg_desc['Version']]
    else:    
        mqmd_dict['Version'] = msg_desc['Version']
    
    if pretty_mqmd and mqmd_dicts["mqro"].has_key(msg_desc['Report']):
        mqmd_dict['Report'] =  mqmd_dicts["mqro"][msg_desc['Report']]
    else:
        mqmd_dict['Report'] = msg_desc['Report']
        
    if pretty_mqmd and mqmd_dicts["mqmt"].has_key(msg_desc['MsgType']):
        mqmd_dict['MsgType'] =  mqmd_dicts["mqmt"][msg_desc['MsgType']]
    else:
        mqmd_dict['MsgType'] = msg_desc['MsgType']
    
    if pretty_mqmd and mqmd_dicts["mqei"].has_key(msg_desc['Expiry']):
        mqmd_dict['Expiry'] =  mqmd_dicts["mqei"][msg_desc['Expiry']]
    else:
        mqmd_dict['Expiry'] = msg_desc['Expiry']
    
    if pretty_mqmd and mqmd_dicts["mqfb"].has_key(msg_desc['Feedback']):
        mqmd_dict['Feedback'] =  mqmd_dicts["mqfb"][msg_desc['Feedback']]
    else:
        mqmd_dict['Feedback'] = msg_desc['Feedback']

    if pretty_mqmd and mqmd_dicts["mqenc"].has_key(msg_desc['Encoding']):
        mqmd_dict['Encoding'] =  mqmd_dicts["mqenc"][msg_desc['Encoding']]
    else:
        mqmd_dict['Encoding'] = msg_desc['Encoding']
    
    if pretty_mqmd and mqmd_dicts["mqccsi"].has_key(msg_desc['CodedCharSetId']):
        mqmd_dict['CodedCharSetId'] =  mqmd_dicts["mqccsi"][msg_desc['CodedCharSetId']]
    else:
        mqmd_dict['CodedCharSetId'] = msg_desc['CodedCharSetId']
    
    if pretty_mqmd and mqmd_dicts["mqfmt"].has_key(msg_desc['Format']):
        mqmd_dict['Format'] =  mqmd_dicts["mqfmt"][msg_desc['Format']]
    else:
        mqmd_dict['Format'] = msg_desc['Format']
    
    if pretty_mqmd and mqmd_dicts["mqpri"].has_key(msg_desc['Priority']):
        mqmd_dict['Priority'] =  mqmd_dicts["mqpri"][msg_desc['Priority']]
    else:
        mqmd_dict['Priority'] = msg_desc['Priority']
        
    if pretty_mqmd and mqmd_dicts["mqper"].has_key(msg_desc['Persistence']):
        mqmd_dict['Persistence'] =  mqmd_dicts["mqper"][msg_desc['Persistence']]
    else:
        mqmd_dict['Persistence'] = msg_desc['Persistence']
        
    if pretty_mqmd and mqmd_dicts["mqat"].has_key(msg_desc['PutApplType']):
        mqmd_dict['PutApplType'] =  mqmd_dicts["mqat"][msg_desc['PutApplType']]
    else:
        mqmd_dict['PutApplType'] = msg_desc['PutApplType']
        
    if pretty_mqmd and mqmd_dicts["mqmf"].has_key(msg_desc['MsgFlags']):
        mqmd_dict['MsgFlags'] =  mqmd_dicts["mqmf"][msg_desc['MsgFlags']]
    else:
        mqmd_dict['MsgFlags'] = msg_desc['MsgFlags']

    if pretty_mqmd and mqmd_dicts["mqol"].has_key(msg_desc['OriginalLength']):
        mqmd_dict['OriginalLength'] =  mqmd_dicts["mqol"][msg_desc['OriginalLength']]
    else:
        mqmd_dict['OriginalLength'] = msg_desc['OriginalLength']
    
    if make_mqmd_printable:
        mqmd_dict['MsgId'] = make_printable(msg_desc['MsgId'])
        mqmd_dict['CorrelId'] = make_printable(msg_desc['CorrelId'])
        mqmd_dict['BackoutCount'] = msg_desc['BackoutCount']
        mqmd_dict['ReplyToQ'] = msg_desc['ReplyToQ']
        mqmd_dict['ReplyToQMgr'] = msg_desc['ReplyToQMgr']
        mqmd_dict['UserIdentifier'] = make_printable(msg_desc['UserIdentifier'])
        mqmd_dict['AccountingToken'] = make_printable(msg_desc['AccountingToken'])
        mqmd_dict['ApplIdentityData'] = make_printable(msg_desc['ApplIdentityData'])
        mqmd_dict['PutApplName'] = make_printable(msg_desc['PutApplName'])
        mqmd_dict['PutDate'] = msg_desc['PutDate']
        mqmd_dict['PutTime'] = msg_desc['PutTime']
        mqmd_dict['ApplOriginData'] = (msg_desc['ApplOriginData'])
        mqmd_dict['GroupId'] = make_printable(msg_desc['GroupId'])
        mqmd_dict['MsgSeqNumber'] = msg_desc['MsgSeqNumber']
        mqmd_dict['Offset'] = msg_desc['Offset']

    else:    
        mqmd_dict['MsgId'] = binascii.hexlify(msg_desc['MsgId'])
        mqmd_dict['CorrelId'] = binascii.hexlify(msg_desc['CorrelId'])
        mqmd_dict['BackoutCount'] = msg_desc['BackoutCount']
        mqmd_dict['ReplyToQ'] = msg_desc['ReplyToQ']
        mqmd_dict['ReplyToQMgr'] = msg_desc['ReplyToQMgr']
        mqmd_dict['UserIdentifier'] = binascii.hexlify(msg_desc['UserIdentifier'])
        mqmd_dict['AccountingToken'] = binascii.hexlify(msg_desc['AccountingToken'])
        mqmd_dict['ApplIdentityData'] = binascii.hexlify(msg_desc['ApplIdentityData'])
        mqmd_dict['PutApplName'] = binascii.hexlify(msg_desc['PutApplName'])
        mqmd_dict['PutDate'] = msg_desc['PutDate']
        mqmd_dict['PutTime'] = msg_desc['PutTime']
        mqmd_dict['ApplOriginData'] = (msg_desc['ApplOriginData'])
        mqmd_dict['GroupId'] = binascii.hexlify(msg_desc['GroupId'])
        mqmd_dict['MsgSeqNumber'] = msg_desc['MsgSeqNumber']
        mqmd_dict['Offset'] = msg_desc['Offset']

    return mqmd_dict

# prints XML stream
def print_xml_single_instance_mode(server, event):
    
    print "<stream><event><data>%s</data><host>%s</host></event></stream>" % (
        encodeXMLText(event), server)
    
# prints XML stream
def print_xml_multi_instance_mode(server, event, stanza):
    
    print "<stream><event stanza=""%s""><data>%s</data><host>%s</host></event></stream>" % (
        stanza, encodeXMLText(event), server)
    
# prints simple stream
def print_simple(s):
    print "%s\n" % s
                             
#HELPER FUNCTIONS
    
# prints XML stream
def print_xml_stream(s):
    print "<stream><event unbroken=\"1\"><data>%s</data><done/></event></stream>" % encodeXMLText(s)

def encodeXMLText(text):
    text = text.replace("&", "&amp;")
    text = text.replace("\"", "&quot;")
    text = text.replace("'", "&apos;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("\n", "")
    return text


class BrokerEventResponseHandler:
    """
    IBM Message Broker Monitoring event handler.   
    
    This addon parses a Message Broker monitoring event and extracts the required fields.  
    
    include_complex_top_level = true/false - Include the complex type top level element when logged.
    include_bitstream = true/false - Include the bitstream (base64 or blob) in the splunk event.
    write_events = true/false - Write out the events to disk.  
    gzip_events = true/false - Gzip the events written to disk.
    write_events_folder = "/opt/esb/brokerevents"- Directory to which events must be written.    
    """   
    
    def __init__(self,**args):
        self.args = args
        
        self.include_complex_top_level = False
        if self.args.has_key("include_complex_top_level"):
            if self.args["include_complex_top_level"].lower().strip() == "false":
                self.include_complex_top_level = False
            else:
                self.include_complex_top_level = True
        
        self.include_bitstream = False
        if self.args.has_key("include_bitstream"):
            if self.args["include_bitstream"].lower().strip() == "false":
                self.include_bitstream = False
            else:
                self.include_bitstream = True
        
        self.write_events = True 
        if self.args.has_key("write_events"):
            if self.args["write_events"].lower().strip() == "false":
                self.write_events = False
            else:
                self.write_events = True
            
        self.gzip_events = True 
        if self.args.has_key("gzip_events"):
            if self.args["gzip_events"].lower().strip() == "false":
                self.gzip_events = False
            else:
                self.gzip_events = True
        
        self.write_events_folder = "/opt/splunk/esb/brokerevents"
        if self.args.has_key("write_events_folder"):
            self.write_events_folder = self.args["write_events_folder"]
        
        self.use_event_time = True
        if self.args.has_key("use_event_time"):
            if self.args["use_event_time"].lower().strip() == "false":
                self.use_event_time = False
            else:
                self.use_event_time = True
                
        self.regex = re.compile(r"/[A-Za-z0-9]*:")   
        
    def __call__(self, splunk_host, queue_manager_name, queue, msg_data, msg_desc, from_trigger, **kw):        
        
        splunk_event =""
        event_file_name = ""
        
        queue_manager_name_str = 'queue_manager="%s" ' % queue_manager_name
        queue_str = 'queue="%s" ' % queue
        host = splunk_host + " "
        process = "mqinput(%i): " % os.getpid() 
        
        ev_pos = msg_data.find(":event")
        start_pos = msg_data.rfind("<", 0, ev_pos)

        msg_data = msg_data[start_pos:]
        logging.debug("Msg data: [%s]" % msg_data[:100])
        index_time_o = datetime.datetime.now()
        index_time = "[" + index_time_o.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + time.strftime("%z") + "] "      
        
        if self.write_events:
            try:
                date_s = time.strftime("%Y%m%d")
                cur_folder = os.path.join(os.path.join(os.path.join(self.write_events_folder, queue_manager_name), queue), date_s) 
                
                if not os.path.exists(cur_folder):
                    os.makedirs(cur_folder)
                
                file_name = "BrokerEvent_" +  binascii.hexlify(msg_desc["MsgId"]) + ".xml"
                full_file_name = os.path.join(cur_folder, file_name)
                if self.gzip_events:
                    f = gzip.open(full_file_name + ".gz", 'wb')
                    f.write(msg_data)
                    f.close()
                else:
                    f = open(full_file_name, "w")
                    f.write(msg_data)
                    f.close()
                event_file_name = ' event_file_name="%s"'  % full_file_name
            except Exception, ex:
                logging.error("Failed to write event message. " + str(ex))
        
        try: 
               
            WMBNAMESPACE = u"http://www.ibm.com/xmlns/prod/websphere/messagebroker/6.1.0/monitoring/event"
            nss = {'wmb': WMBNAMESPACE}
            
            doc = lxml.etree.fromstring(msg_data)
            
            if self.use_event_time:
                nl = doc.xpath(u"//wmb:eventSequence[1]/@wmb:creationTime", namespaces=nss)
                if len(nl) > 0:
                    "2015-05-17T06:28:18.535424Z"
                    event_time = datetime.datetime.strptime(nl[0].replace("T", " ").replace("Z", "GMT"), "%Y-%m-%d %H:%M:%S.%f%Z")
    
                    index_time_o = event_time - datetime.timedelta(seconds=time.timezone)
        
                    h_secs = msg_desc["PutTime"][6:]
                    index_time = "[" + index_time_o.strftime("%Y-%m-%d %H:%M:%S") + "." + h_secs + "0 " +  time.strftime("%z") + "] "
            
            broker = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:broker/@wmb:name", namespaces=nss)
            if len(nl) > 0:
                broker = 'broker="%s" ' % nl[0]
                
            exec_group = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:executionGroup/@wmb:name", namespaces=nss)
            if len(nl) > 0:
                exec_group = 'execgroup="%s" ' % nl[0]
                
            flow = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:messageFlow/@wmb:name", namespaces=nss)
            if len(nl) > 0:
                flow = 'flow="%s" ' % nl[0]
                         
            node_details = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:node", namespaces=nss)
            if len(nl) > 0:
                node_label = nl[0].attrib["{%s}nodeLabel" % WMBNAMESPACE]
                node_type = nl[0].attrib["{%s}nodeType" % WMBNAMESPACE]
                node_terminal = nl[0].attrib["{%s}terminal" % WMBNAMESPACE]
                
                node_details = 'node="%s" node_type="%s" node_terminal="%s"' % (node_label, node_type, node_terminal)
    
            
            complex_content = ''
            nl = doc.xpath(u"//wmb:applicationData/wmb:complexContent", namespaces=nss)
            if len(nl) > 0:
                for n in nl:
                    path = ""
                    
                    for c in n:
                        print n.attrib
                        c_name = n.xpath("@wmb:elementName", namespaces=nss)
                        top_level_name = ""
                        if len(c_name):
                            top_level_name = c_name[0]
                        
                        tree = lxml.etree.ElementTree(c)
                        for e in tree.iter():
                            if e.text is not None:
                                if e.text.strip() != "":
                                    path = tree.getpath(e)
                                    path = self.regex.sub("/", path)
                                    
                                    if not self.include_complex_top_level:
                                        path = path.replace("/%s/" % top_level_name, "")
                                    else:
                                        if path[0] == "/":
                                            path = path[1:]
                                    
                                    path = path.replace("/", ".")
    
                                    complex_content = complex_content + '%s="%s" ' % (path, e.text.strip())
            
            simple_content = ""
            nl = doc.xpath(u"//wmb:applicationData/wmb:simpleContent", namespaces=nss)
            if len(nl) > 0:
                nameTuple = u"{%s}name" % WMBNAMESPACE
                valueTuple = u"{%s}value" % WMBNAMESPACE
                
                for n in nl:
                    name = None
                    value = None
                    if n.attrib.has_key(nameTuple):
                        name = n.attrib[nameTuple] 
                    if n.attrib.has_key(valueTuple):
                        value = n.attrib[valueTuple]
                   
                    if value is not None:
                        simple_content = simple_content + '%s="%s" ' % (name, value.strip())
                        
            #handle trigger
            if from_trigger:
                pass
            else:  
                splunk_event = splunk_event + index_time + host + process + queue_manager_name_str + queue_str + broker + exec_group + flow + node_details +  complex_content + simple_content + event_file_name
                print_xml_single_instance_mode(splunk_host, splunk_event)
                
        except Exception, ex:
            logging.error("Exception occured! Exception:" + str(ex))
            splunk_event = splunk_event + index_time + host + process + queue_manager_name_str + queue_str + event_file_name + ' error="Exception occured while processing event. Exception Text: %s"' % (str(ex))
            print_xml_single_instance_mode(splunk_host, splunk_event)
               