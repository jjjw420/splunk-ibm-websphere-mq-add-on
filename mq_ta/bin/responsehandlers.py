'''
IBM Websphere MQ Modular Input for Splunk
Hannes Wagener - 2015

Used the Splunk provided modular input as example.

Add response handlers to perform specific functions here.

DISCLAIMER
You are free to use this code in any way you like, subject to the
Python & IBM disclaimers & copyrights. I make no representations
about the suitability of this software for any purpose. It is
provided "AS-IS" without warranty of any kind, either express or
implied.

'''
from __future__ import print_function

import json
import datetime
import time
import binascii
import base64
import string
import os
import lxml
import logging
import gzip
import re

import pymqi
from pymqi import CMQC as CMQC

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s %(message)s')


#####################################
# Queue Input Response handlers
#####################################

class DefaultQueueResponseHandler(object):
    """"
    The DefaultResponseHandler uses the "syslog" input type and
    supports the following options:

    DefaultQueuResponseHandler arguments:
        include_payload=false/true - Include the message payload in the event.
        Default: true

        use_mqmd_puttime=false/true - Use the message put time as the
        event time.  Default: true

        include_mqmd=false/true - Include the MQMD in the event.
        Default: false

        pretty_mqmd=false/true - Use textual descriptions for MQMD values.
        Default: true

        make_mqmd_printable=false/true - Escape non text values in the MQMD.
        Default: true

        payload_limit=1024 - How many bytes of the payload to include
        in the splunk event. Default: 1024 (1kb)

        encode_payload=false/base64/hexbinary - Encode the payload.
        Default: false

        make_payload_printable=false/true - Escape non text values in
        the payload.  Default: true

    """

    def __init__(self, **args):

        #logging.error("default queue handler _init_")
        self.args = args
        self.mqmd_dicts = None

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

        self.mqmd_dicts = {"mqmd": mqmd_dict, "mqro": mqro_dict,
                           "mqmt": mqmt_dict, "mqei": mqei_dict,
                           "mqfb": mqfb_dict, "mqenc": mqenc_dict,
                           "mqccsi": mqccsi_dict, "mqfmt": mqfmt_dict,
                           "mqpri": mqpri_dict, "mqper": mqper_dict,
                           "mqat": mqat_dict, "mqmf": mqmf_dict,
                           "mqol": mqol_dict}

        if "include_mqmd" in self.args:
            if self.args["include_mqmd"].lower().strip() == "true":
                self.include_mqmd = True
            else:
                self.include_mqmd = False
        else:
            self.include_mqmd = False

        if "pretty_mqmd" in self.args:
            if self.args["pretty_mqmd"].strip().lower() == "true":
                self.pretty_mqmd = True
            else:
                self.pretty_mqmd = False
        else:
            self.pretty_mqmd = True

        if "use_mqmd_puttime" in self.args:
            if self.args["use_mqmd_puttime"].lower().strip() == "true":
                self.use_mqmd_puttime = True
            else:
                self.use_mqmd_puttime = False
        else:
            self.use_mqmd_puttime = True

        if "include_payload" in self.args:
            if self.args["include_payload"].lower().strip() == "true":
                self.include_payload = True
            else:
                self.include_payload = False
        else:
            self.include_payload = True

        if "payload_limit" in self.args:
            try:
                self.payload_limit = int(self.args["payload_limit"].strip())
            except:
                self.payload_limit = 0
        else:
            self.payload_limit = 1024

        if "encode_payload" in self.args:
            self.encode_payload = self.args["encode_payload"].lower().strip()
        else:
            self.encode_payload = "false"

        if "make_mqmd_printable" in self.args:
            if self.args["make_mqmd_printable"].lower().strip() == "true":
                self.make_mqmd_printable = True
            else:
                self.make_mqmd_printable = False
        else:
            self.make_mqmd_printable = True

        if "make_payload_printable" in self.args:
            if self.args["make_payload_printable"].lower().strip() == "true":
                self.make_payload_printable = True
            else:
                self.make_payload_printable = False
        else:
            self.make_payload_printable = True

    def __call__(self, splunk_host, queue_manager_name, queue, msg_data,
                 msg_desc, from_trigger, **kw):

        splunk_event = ""
        #logging.error("default queue handler _call_")
        mqmd_str = ""
        if self.include_mqmd and (msg_desc is not None):
            new_mqmd = make_mqmd(msg_desc, self.mqmd_dicts,
                                 self.pretty_mqmd,
                                 self.make_mqmd_printable)
            for (mqmd_key, mqmd_value) in list(new_mqmd.items()):
                if isinstance(mqmd_value, int) or \
                    isinstance(mqmd_value, float) or \
                        str(mqmd_value).startswith("MQ"):
                    mqmd_str = mqmd_str + \
                                " %s=%s" % (str(mqmd_key).strip(),
                                            str(mqmd_value))
                else:
                    mqmd_str = mqmd_str + \
                                ' %s="%s"' % (str(mqmd_key).strip(),
                                              str(mqmd_value))

        index_time = "[" + \
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + \
            " " + time.strftime("%z") + "]"

        if self.use_mqmd_puttime:
            puttime = datetime.datetime.strptime(msg_desc["PutDate"] +
                                                 " " +
                                                 msg_desc["PutTime"][0:6],
                                                 "%Y%m%d %H%M%S")
            # puttime = puttime.replace(tzinfo=pytz.timezone("GMT"))
            localtime = puttime - datetime.timedelta(seconds=time.timezone)

            h_secs = msg_desc["PutTime"][6:]
            index_time = "[" + localtime.strftime("%Y-%m-%d %H:%M:%S") + \
                         "." + h_secs + "0 " + \
                         time.strftime("%z") + "]"

        payload = ""
        logging.debug("B4 include payload.")
        if self.include_payload:
            if self.encode_payload == "base64":
                payload = ' payload="%s"' % \
                    str(base64.encodestring(msg_data[:self.payload_limit]))
            else:
                if self.encode_payload == "hexbinary":
                    payload = ' payload="%s"' % \
                        str(binascii.hexlify(msg_data[:self.payload_limit]))
                else:
                    if self.make_payload_printable:
                        payload = ' payload="%s"' % \
                            make_printable(msg_data[:self.payload_limit])
                    else:
                        payload = ' payload="%s"' % \
                            msg_data[:self.payload_limit]

        queue_manager_name_str = " queue_manager=%s" % queue_manager_name
        queue = " queue=%s" % queue
        host = " " + splunk_host
        process = " mqinput(%i):" % os.getpid()

        # handle trigger
        if from_trigger:
            pass
        else:
            splunk_event = splunk_event + index_time + host + process + \
                           queue_manager_name_str + queue + mqmd_str + \
                           payload
            print_xml_single_instance_mode(splunk_host, splunk_event)


class JSONFormatterResponseHandler(object):

    def __init__(self, **args):
        pass

    def __call__(self, response_object, destination, table=False,
                 from_trap=False, trap_metadata=None, split_bulk_output=False,
                 mibView=None):
        # handle tables
        if table:
            values = []
            for varBindTableRow in response_object:
                row = {}
                for name, val in varBindTableRow:
                    row[name.prettyPrint()] = val.prettyPrint()
                values.append(row)
            print_xml_single_instance_mode(destination, json.dumps(values))
        # handle scalars
        else:
            values = {}
            for name, val in response_object:
                values[name.prettyPrint()] = val.prettyPrint()
            print_xml_single_instance_mode(destination, json.dumps(values))


def is_printable(char):
    '''Return true if the character char is printable or false
       if it is not printable.
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

    logging.debug("Make mqmd.")

    mqmd_dict = {}

    if mqmd_dicts is None:
        logging.debug("Make mqmd. mqmd_dicts is None")

    if msg_desc is None:
        logging.debug("Make mqmd. msg_desc is None")

    if pretty_mqmd and msg_desc['StrucId'] in mqmd_dicts["mqmd"]:
        mqmd_dict['StrucId'] = mqmd_dicts["mqmd"][msg_desc['StrucId']]
    else:
        mqmd_dict['StrucId'] = msg_desc['StrucId']

    logging.debug("Make mqmd. after StrucId.")
    if pretty_mqmd and msg_desc['Version'] in mqmd_dicts["mqmd"]:
        mqmd_dict['Version'] = mqmd_dicts["mqmd"][msg_desc['Version']]
    else:
        mqmd_dict['Version'] = msg_desc['Version']

    if pretty_mqmd and msg_desc['Report'] in mqmd_dicts["mqro"]:
        mqmd_dict['Report'] = mqmd_dicts["mqro"][msg_desc['Report']]
    else:
        mqmd_dict['Report'] = msg_desc['Report']

    if pretty_mqmd and msg_desc['MsgType'] in mqmd_dicts["mqmt"]:
        mqmd_dict['MsgType'] = mqmd_dicts["mqmt"][msg_desc['MsgType']]
    else:
        mqmd_dict['MsgType'] = msg_desc['MsgType']

    if pretty_mqmd and msg_desc['Expiry'] in mqmd_dicts["mqei"]:
        mqmd_dict['Expiry'] = mqmd_dicts["mqei"][msg_desc['Expiry']]
    else:
        mqmd_dict['Expiry'] = msg_desc['Expiry']

    if pretty_mqmd and msg_desc['Feedback'] in mqmd_dicts["mqfb"]:
        mqmd_dict['Feedback'] = mqmd_dicts["mqfb"][msg_desc['Feedback']]
    else:
        mqmd_dict['Feedback'] = msg_desc['Feedback']

    if pretty_mqmd and msg_desc['Encoding'] in mqmd_dicts["mqenc"]:
        mqmd_dict['Encoding'] = mqmd_dicts["mqenc"][msg_desc['Encoding']]
    else:
        mqmd_dict['Encoding'] = msg_desc['Encoding']

    logging.debug("Make mqmd. After encoding.")

    if pretty_mqmd and \
       msg_desc['CodedCharSetId'] in mqmd_dicts["mqccsi"]:
        mqmd_dict['CodedCharSetId'] = \
            mqmd_dicts["mqccsi"][msg_desc['CodedCharSetId']]
    else:
        mqmd_dict['CodedCharSetId'] = msg_desc['CodedCharSetId']

    if pretty_mqmd and msg_desc['Format'] in mqmd_dicts["mqfmt"]:
        mqmd_dict['Format'] = mqmd_dicts["mqfmt"][msg_desc['Format']]
    else:
        mqmd_dict['Format'] = msg_desc['Format']

    if pretty_mqmd and msg_desc['Priority'] in mqmd_dicts["mqpri"]:
        mqmd_dict['Priority'] = mqmd_dicts["mqpri"][msg_desc['Priority']]
    else:
        mqmd_dict['Priority'] = msg_desc['Priority']

    logging.debug("Make mqmd. After Priority.")

    if pretty_mqmd and msg_desc['Persistence'] in mqmd_dicts["mqper"]:
        mqmd_dict['Persistence'] = mqmd_dicts["mqper"][msg_desc['Persistence']]
    else:
        mqmd_dict['Persistence'] = msg_desc['Persistence']

    if pretty_mqmd and msg_desc['PutApplType'] in mqmd_dicts["mqat"]:
        mqmd_dict['PutApplType'] = mqmd_dicts["mqat"][msg_desc['PutApplType']]
    else:
        mqmd_dict['PutApplType'] = msg_desc['PutApplType']

    if pretty_mqmd and msg_desc['MsgFlags'] in mqmd_dicts["mqmf"]:
        mqmd_dict['MsgFlags'] = mqmd_dicts["mqmf"][msg_desc['MsgFlags']]
    else:
        mqmd_dict['MsgFlags'] = msg_desc['MsgFlags']

    logging.debug("Make mqmd. After MsgFlags.")

    if pretty_mqmd and msg_desc['OriginalLength'] in mqmd_dicts["mqol"]:
        mqmd_dict['OriginalLength'] = \
            mqmd_dicts["mqol"][msg_desc['OriginalLength']]
    else:
        mqmd_dict['OriginalLength'] = msg_desc['OriginalLength']

    logging.debug("B4 make printable.")

    if make_mqmd_printable:
        mqmd_dict['MsgId'] = make_printable(msg_desc['MsgId'])
        mqmd_dict['CorrelId'] = make_printable(msg_desc['CorrelId'])
        mqmd_dict['BackoutCount'] = msg_desc['BackoutCount']
        mqmd_dict['ReplyToQ'] = msg_desc['ReplyToQ'].strip()
        mqmd_dict['ReplyToQMgr'] = msg_desc['ReplyToQMgr'].strip()
        mqmd_dict['UserIdentifier'] = \
            make_printable(msg_desc['UserIdentifier'])
        mqmd_dict['AccountingToken'] = \
            make_printable(msg_desc['AccountingToken'])
        mqmd_dict['ApplIdentityData'] = \
            make_printable(msg_desc['ApplIdentityData'])
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
        mqmd_dict['ReplyToQ'] = msg_desc['ReplyToQ'].strip()
        mqmd_dict['ReplyToQMgr'] = msg_desc['ReplyToQMgr'].strip()
        mqmd_dict['UserIdentifier'] = \
            binascii.hexlify(msg_desc['UserIdentifier'])
        mqmd_dict['AccountingToken'] = \
            binascii.hexlify(msg_desc['AccountingToken'])
        mqmd_dict['ApplIdentityData'] = \
            binascii.hexlify(msg_desc['ApplIdentityData'])
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

    print("<stream><event><data>%s</data><host>%s</host></event></stream>" % (
        encodeXMLText(event), server))


# prints XML stream
def print_xml_multi_instance_mode(server, event, stanza):

    print("<stream><event stanza=""%s""><data>%s</data><host>%s</host>\
</event></stream>" % (stanza, encodeXMLText(event), server))


# prints simple stream
def print_simple(s):
    print("%s\n" % s)


# HELPER FUNCTIONS
# prints XML stream
def print_xml_stream(s):
    print("<stream><event unbroken=\"1\"><data>%s</data><done/></event>\
</stream>" % encodeXMLText(s))


def encodeXMLText(text):
    text = text.replace("&", "&amp;")
    text = text.replace("\"", "&quot;")
    text = text.replace("'", "&apos;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("\n", "")
    return text


class BrokerEventResponseHandler(object):
    """
    include_complex_top_level = true/false
    include_bitstream = true/false
    write_events = true/false
    gzip_events = true/false
    write_events_folder = "/opt/esb/brokerevents"
    """

    def __init__(self, **args):
        self.args = args

        self.include_complex_top_level = False
        if "include_complex_top_level" in self.args:
            if self.args["include_complex_top_level"].lower().strip() == \
                    "true":
                self.include_complex_top_level = True
            else:
                self.include_complex_top_level = False

        self.include_bitstream = True
        if "include_bitstream" in self.args:
            if self.args["include_bitstream"].lower().strip() == "false":
                self.include_bitstream = False
            else:
                self.include_bitstream = True

        self.write_events = False
        if "write_events" in self.args:
            if self.args["write_events"].lower().strip() == "true":
                self.write_events = True
            else:
                self.write_events = False

        self.gzip_events = True
        if "gzip_events" in self.args:
            if self.args["gzip_events"].lower().strip() == "false":
                self.gzip_events = False
            else:
                self.gzip_events = True

        self.write_events_folder = "/opt/splunk/esb/brokerevents"
        if "write_events_folder" in self.args:
            self.write_events_folder = self.args["write_events_folder"]

        self.use_event_time = True
        if "use_event_time" in self.args:
            if self.args["use_event_time"].lower().strip() == "false":
                self.use_event_time = False
            else:
                self.use_event_time = True

        self.regex = re.compile(r"/[A-Za-z0-9]*:")

    def __call__(self, splunk_host, queue_manager_name, queue, msg_data,
                 msg_desc, from_trigger, **kw):

        splunk_event = ""
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
        index_time = "[" + \
            index_time_o.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + \
            " " + time.strftime("%z") + "] "

        if self.write_events:
            try:
                date_s = time.strftime("%Y%m%d")
                cur_folder = \
                    os.path.join(os.path.join(
                        os.path.join(
                            self.write_events_folder, queue_manager_name),
                        queue), date_s)

                if not os.path.exists(cur_folder):
                    os.makedirs(cur_folder)

                file_name = "BrokerEvent_" + \
                    binascii.hexlify(msg_desc["MsgId"]) + ".xml"
                full_file_name = os.path.join(cur_folder, file_name)
                if self.gzip_events:
                    f = gzip.open(full_file_name + ".gz", 'wb')
                    f.write(msg_data)
                    f.close()
                else:
                    f = open(full_file_name, "w")
                    f.write(msg_data)
                    f.close()
                event_file_name = ' event_file_name="%s"' % \
                    full_file_name
            except Exception as ex:
                logging.error("Failed to write event message. " + str(ex))

        try:

            WMBNAMESPACE = \
                u"http://www.ibm.com/xmlns/prod/websphere/messagebroker/6.1.0/monitoring/event"
            nss = {'wmb': WMBNAMESPACE}

            doc = lxml.etree.fromstring(msg_data)

            if self.use_event_time:
                nl = doc.xpath(u"//wmb:eventSequence[1]/@wmb:creationTime",
                               namespaces=nss)
                if len(nl) > 0:
                    "2015-05-17T06:28:18.535424Z"
                    event_time = \
                        datetime.datetime.strptime(
                            nl[0].replace("T", " ").replace("Z", "GMT"),
                            "%Y-%m-%d %H:%M:%S.%f%Z")

                    index_time_o = event_time - \
                        datetime.timedelta(seconds=time.timezone)

                    h_secs = msg_desc["PutTime"][6:]
                    index_time = "[" + \
                        index_time_o.strftime("%Y-%m-%d %H:%M:%S") + "." + \
                        h_secs + "0 " + time.strftime("%z") + "] "

            broker = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:broker/@wmb:name",
                           namespaces=nss)
            if len(nl) > 0:
                broker = 'broker="%s" ' % nl[0]

            exec_group = ""
            nl = doc.xpath(
                u"//wmb:messageFlowData[1]/wmb:executionGroup/@wmb:name",
                namespaces=nss)
            if len(nl) > 0:
                exec_group = 'execgroup="%s" ' % nl[0]

            flow = ""
            nl = doc.xpath(
                u"//wmb:messageFlowData[1]/wmb:messageFlow/@wmb:name",
                namespaces=nss)
            if len(nl) > 0:
                flow = 'flow="%s" ' % nl[0]

            node_details = ""
            nl = doc.xpath(u"//wmb:messageFlowData[1]/wmb:node",
                           namespaces=nss)
            if len(nl) > 0:
                node_details = ""
                if "{%s}nodeLabel" % WMBNAMESPACE in nl[0].attrib:
                    node_label = nl[0].attrib["{%s}nodeLabel" % WMBNAMESPACE]
                    node_details = node_details + 'node="%s" ' % node_label

                if "{%s}nodeType" % WMBNAMESPACE in nl[0].attrib:
                    node_type = nl[0].attrib["{%s}nodeType" % WMBNAMESPACE]
                    node_details = node_details + 'node_type="%s" ' % node_type

                if "{%s}terminal" % WMBNAMESPACE in nl[0].attrib:
                    node_terminal = nl[0].attrib["{%s}terminal" % WMBNAMESPACE]
                    node_details = node_details + 'node_terminal="%s" ' % \
                        node_terminal
                # node_details = 'node="%s" node_type="%s"
                # node_terminal="%s"' % (node_label, node_type, node_terminal)

            complex_content = ''
            nl = doc.xpath(u"//wmb:applicationData/wmb:complexContent",
                           namespaces=nss)
            if len(nl) > 0:
                for n in nl:
                    path = ""

                    for c in n:
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
                                        path = \
                                            path.replace(
                                                "/%s/" % top_level_name,
                                                "")
                                    else:
                                        if path[0] == "/":
                                            path = path[1:]

                                    path = path.replace("/", ".")

                                    complex_content = complex_content + \
                                        '%s="%s" ' % (path, e.text.strip())

            simple_content = ""
            nl = doc.xpath(u"//wmb:applicationData/wmb:simpleContent",
                           namespaces=nss)
            if len(nl) > 0:
                nameTuple = u"{%s}name" % WMBNAMESPACE
                valueTuple = u"{%s}value" % WMBNAMESPACE

                for n in nl:
                    name = None
                    value = None
                    if nameTuple in n.attrib:
                        name = n.attrib[nameTuple]
                    if valueTuple in n.attrib:
                        value = n.attrib[valueTuple]

                    if value is not None:
                        simple_content = simple_content + \
                            '%s="%s" ' % (name, value.strip())

            bitstream_data = ""
            bitstream_encoding = ""
            # arb_text = "include_bitstream={} ".format(self.include_bitstream)
            #logging.error("Include bitstream:" + str(self.include_bitstream))
            # sys.stderr.write("Include bitstream:" + \
            # str(self.include_bitstream) + "\n")
            if self.include_bitstream:
                nl = doc.xpath("//wmb:bitstream", namespaces=nss)
                #logging.error("len is:" + str(len(nl)))
                if len(nl) > 0:
                    encoding_key = "{%s}encoding" % WMBNAMESPACE
                    if encoding_key in nl[0].attrib:
                        bitstream_encoding = 'bitstream_encoding="%s" '
                        bitstream_encoding = \
                            bitstream_encoding % (nl[0].attrib[encoding_key])
                    bitstream_data = 'bitstream_data="{}" '
                    bitstream_data = bitstream_data.format(nl[0].text)
            # handle trigger
            if from_trigger:
                pass
            else:
                splunk_event = splunk_event + index_time + host + \
                               process + queue_manager_name_str + queue_str + \
                               broker + exec_group + flow + node_details + \
                               complex_content + simple_content + \
                               event_file_name + bitstream_encoding + \
                               bitstream_data
                print_xml_single_instance_mode(splunk_host, splunk_event)

        except Exception as ex:
            logging.error("Exception occured! Exception:" + str(ex))
            splunk_event = splunk_event + index_time + host + process + \
                queue_manager_name_str + queue_str + event_file_name + \
                ' error="Exception occured while processing event. Exception Text: %s"' % (str(ex))
            print_xml_single_instance_mode(splunk_host, splunk_event)


#####################################
# Channel Status Response handlers
#####################################


class DefaultChannelStatusResponseHandler(object):

    """
    The default channel status handler.  Uses PCF to query the channel status.

    DefaultChannelStatusHandler arguments:
        include_zero_values=true/false - Include values that are set to
        zero or default values in the event.  Default: false

        textual_values=true/false - Include the textual description for
        channel status parameters.  Default: true
    """

    def __init__(self, **args):
        self.args = args

        if "include_zero_values" in self.args:
            if self.args["include_zero_values"].lower().strip() == "true":
                self.include_zero_values = True
            else:
                self.include_zero_values = False
        else:
            self.include_zero_values = False

        if "textual_values" in self.args:
            if self.args["textual_values"].lower().strip() == "true":
                self.textual_values = True
            else:
                self.textual_values = False
        else:
            self.textual_values = True

        if self.textual_values:
            self.channel_compression_descs = {
                pymqi.CMQXC.MQCOMPRESS_NOT_AVAILABLE: "NOT_AVAILABLE",
                pymqi.CMQXC.MQCOMPRESS_NONE: "NONE",
                pymqi.CMQXC.MQCOMPRESS_RLE: "RLE",
                pymqi.CMQXC.MQCOMPRESS_ZLIBFAST: "ZLIBFAST",
                pymqi.CMQXC.MQCOMPRESS_ZLIBHIGH: "ZLIBHIGH",
                pymqi.CMQXC.MQCOMPRESS_SYSTEM: "SYSTEM",
                pymqi.CMQXC.MQCOMPRESS_ANY: "ANY"
                }
            self.channel_monitoring_descs = {
                pymqi.CMQC.MQMON_LOW: "LOW",
                pymqi.CMQC.MQMON_MEDIUM: "MEDIUM",
                pymqi.CMQC.MQMON_HIGH: "HIGH",
                pymqi.CMQC.MQMON_OFF: "OFF",
                pymqi.CMQC.MQMON_Q_MGR: "QMGR"
                }
            self.channel_substate_descs = {
                pymqi.CMQCFC.MQCHSSTATE_OTHER: "OTHER",
                pymqi.CMQCFC.MQCHSSTATE_END_OF_BATCH: "END_OF_BATCH",
                pymqi.CMQCFC.MQCHSSTATE_SENDING: "SENDING",
                pymqi.CMQCFC.MQCHSSTATE_RECEIVING: "RECEIVING",
                pymqi.CMQCFC.MQCHSSTATE_SERIALIZING: "SERIALIZING",
                pymqi.CMQCFC.MQCHSSTATE_RESYNCHING: "RESYNCHING",
                pymqi.CMQCFC.MQCHSSTATE_HEARTBEATING: "HEARTBEATING",
                pymqi.CMQCFC.MQCHSSTATE_IN_SCYEXIT: "IN_SCYEXIT",
                pymqi.CMQCFC.MQCHSSTATE_IN_RCVEXIT: "IN_RCVEXIT",
                pymqi.CMQCFC.MQCHSSTATE_IN_SENDEXIT: "IN_SENDEXIT",
                pymqi.CMQCFC.MQCHSSTATE_IN_MSGEXIT: "IN_MSGEXIT",
                pymqi.CMQCFC.MQCHSSTATE_IN_MREXIT: "IN_MREXIT",
                pymqi.CMQCFC.MQCHSSTATE_IN_CHADEXIT: "IN_CHADEXIT",
                pymqi.CMQCFC.MQCHSSTATE_NET_CONNECTING: "NET_CONNECTING",
                pymqi.CMQCFC.MQCHSSTATE_SSL_HANDSHAKING: "SSL_HANDSHAKING",
                pymqi.CMQCFC.MQCHSSTATE_NAME_SERVER: "NAME_SERVER",
                pymqi.CMQCFC.MQCHSSTATE_IN_MQPUT: "IN_MQPUT",
                pymqi.CMQCFC.MQCHSSTATE_IN_MQGET: "IN_MQGET",
                pymqi.CMQCFC.MQCHSSTATE_IN_MQI_CALL: "IN_MQI_CALL",
                pymqi.CMQCFC.MQCHSSTATE_COMPRESSING: "COMPRESSING"
                }

            self.channel_status_descs = {
                pymqi.CMQCFC.MQCHS_BINDING: "BINDING",
                pymqi.CMQCFC.MQCHS_STARTING: "STARTING",
                pymqi.CMQCFC.MQCHS_RUNNING: "RUNNING",
                pymqi.CMQCFC.MQCHS_STOPPING: "STOPPING",
                pymqi.CMQCFC.MQCHS_RETRYING: "RETRYING"
                }

    def __call__(self, splunk_host, queue_manager_name,
                 conf_channel_name, pcf_response, **kw):
        """
CHANNEL(LDB0.TO.LDB1)                   CHLTYPE(SDR)
BATCHES(457)                            BATCHSZ(50)
BUFSRCVD(459)                           BUFSSENT(2002)
BYTSRCVD(13268)                         BYTSSENT(3472472)
CHSTADA(2016-01-17)                     CHSTATI(01.04.25)
COMPHDR(NONE,NONE)                      COMPMSG(NONE,NONE)
COMPRATE(0,0)                           COMPTIME(0,0)
CONNAME(127.0.0.1(1415))                CURLUWID(80679A56CA090010)
CURMSGS(0)                              CURRENT
CURSEQNO(3003)                          EXITTIME(0,0)
HBINT(300)                              INDOUBT(NO)
JOBNAME(00004A5300000001)               LOCLADDR(127.0.0.1(33842))
LONGRTS(999999999)                      LSTLUWID(80679A56C9090010)
LSTMSGDA(2016-01-17)                    LSTMSGTI(01.05.38)
LSTSEQNO(3003)                          MCASTAT(RUNNING)
MONCHL(LOW)                             MSGS(2000)
NETTIME(25,0)                           NPMSPEED(FAST)
RQMNAME(LDB1)                           SHORTRTS(10)
SSLCERTI( )                             SSLKEYDA( )
SSLKEYTI( )                             SSLPEER( )
SSLRKEYS(0)                             STATUS(RUNNING)
STOPREQ(NO)                             SUBSTATE(MQGET)
XBATCHSZ(2,2)                           XMITQ(LDB1)
XQTIME(3151,1099)

CHANNEL(LDB0.TO.LDB1)                   CHLTYPE(SDR)
BATCHES(1)                              BATCHSZ(50)
BUFSRCVD(2)                             BUFSSENT(5)
BYTSRCVD(272)                           BYTSSENT(1863)
CHSTADA(2016-01-17)                     CHSTATI(01.10.56)
COMPHDR(NONE,NONE)                      COMPMSG(ZLIBFAST,ZLIBFAST)
COMPRATE(82,82)                         COMPTIME(156,156)
CONNAME(127.0.0.1(1415))                CURLUWID(80679A5601100010)
CURMSGS(3)                              CURRENT
CURSEQNO(5003)                          EXITTIME(0,0)
HBINT(300)                              INDOUBT(NO)
JOBNAME(0000506100000001)               LOCLADDR(127.0.0.1(33941))
LONGRTS(999999999)                      LSTLUWID(80679A56C00B0010)
LSTMSGDA(2016-01-17)                    LSTMSGTI(01.10.56)
LSTSEQNO(5000)                          MCASTAT(NOT RUNNING)
MONCHL(LOW)                             MSGS(3)
NETTIME(0,0)                            NPMSPEED(FAST)
RQMNAME(LDB1)                           SHORTRTS(10)
SSLCERTI( )                             SSLKEYDA( )
SSLKEYTI( )                             SSLPEER( )
SSLRKEYS(0)                             STATUS(RETRYING)
STOPREQ(NO)                             SUBSTATE( )
XBATCHSZ(3,3)                           XMITQ(LDB1)
XQTIME(0,0)

MQIACH_BYTES_RECEIVED:236
MQIACH_BATCHES:0
MQIACH_BUFFERS_SENT:1
MQIACH_BUFFERS_RECEIVED:1
MQIACH_LONG_RETRIES_LEFT:999999999
MQIACH_SHORT_RETRIES_LEFT:10
MQIACH_MCA_STATUS:3
MQIACH_STOP_REQUESTED:0
MQIACH_XMITQ_TIME_INDICATOR:[0L, 0L]
MQIACH_NPM_SPEED:2
MQIACH_HB_INTERVAL:300
MQIACH_NETWORK_TIME_INDICATOR:[0L, 0L]
MQIACH_HDR_COMPRESSION:[0L, 0L]
MQIACH_MSG_COMPRESSION:[2L, 0L]
MQCACH_CHANNEL_NAME:LDB0.TO.LDB1
MQCACH_XMIT_Q_NAME:LDB1
MQCACH_CONNECTION_NAME:127.0.0.1(1415)
MQCACH_SSL_CERT_ISSUER_NAME:
MQIACH_CHANNEL_SUBSTATE:1600
MQIACH_SSL_KEY_RESETS:0
MQCACH_LOCAL_ADDRESS:127.0.0.1(41241)
MQCACH_LAST_LUWID:80679A56C21D0010
MQCACH_LAST_MSG_TIME:
MQCACH_LAST_MSG_DATE:
MQIACH_EXIT_TIME_INDICATOR:[0L, 0L]
MQIACH_BATCH_SIZE_INDICATOR:[0L, 0L]
MQCACH_CHANNEL_START_TIME:15.16.27
MQCACH_CHANNEL_START_DATE:2016-01-17
MQCACH_MCA_JOB_NAME:0000740B00000001
MQIACH_COMPRESSION_RATE:[0L, 0L]
MQIACH_COMPRESSION_TIME:[0L, 0L]
MQCACH_SSL_SHORT_PEER_NAME:
MQCACH_CURRENT_LUWID:80679A56011E0010
MQIACH_BATCH_SIZE:50
MQRC_HANDLE_NOT_AVAILABLE:LDB1
MQCACH_SSL_KEY_RESET_DATE:
MQIACH_CHANNEL_TYPE:1
MQCACH_LAST_USED:
MQIACH_CHANNEL_INSTANCE_TYPE:1011
MQIACH_CHANNEL_STATUS:3
MQIACH_INDOUBT_STATUS:0
MQIACH_LAST_SEQUENCE_NUMBER:9003
MQIA_MONITORING_CHANNEL:17
MQIACH_CURRENT_MSGS:0
MQIACH_CURRENT_SEQUENCE_NUMBER:9003
MQIACH_MSGS:0
MQIACH_BYTES_SENT:236


MQCHSSTATE_OTHER = 0
MQCHSSTATE_END_OF_BATCH = 100
MQCHSSTATE_SENDING = 200
MQCHSSTATE_RECEIVING = 300
MQCHSSTATE_SERIALIZING = 400
MQCHSSTATE_RESYNCHING = 500
MQCHSSTATE_HEARTBEATING = 600
MQCHSSTATE_IN_SCYEXIT = 700
MQCHSSTATE_IN_RCVEXIT = 800
MQCHSSTATE_IN_SENDEXIT = 900
MQCHSSTATE_IN_MSGEXIT = 1000
MQCHSSTATE_IN_MREXIT = 1100
MQCHSSTATE_IN_CHADEXIT = 1200
MQCHSSTATE_NET_CONNECTING = 1250
MQCHSSTATE_SSL_HANDSHAKING = 1300
MQCHSSTATE_NAME_SERVER = 1400
MQCHSSTATE_IN_MQPUT = 1500
MQCHSSTATE_IN_MQGET = 1600
MQCHSSTATE_IN_MQI_CALL = 1700
MQCHSSTATE_COMPRESSING = 1800

        """

        for channel_info in pcf_response:

            channel_name = None
            channel_monitoring = None
            network_time = None
            network_time_short = None
            network_time_long = None
            xmitq_time = None
            xmitq_time_short = None
            xmitq_time_long = None
            exit_time = None
            exit_time_short = None
            exit_time_long = None
            bytes_received = None
            bytes_sent = None
            comp_header = None
            comp_header_1 = None
            comp_header_2 = None
            comp_message = None
            comp_message_1 = None
            comp_message_2 = None
            comp_rate = None
            comp_rate_short = None
            comp_rate_long = None
            comp_time = None
            comp_time_short = None
            comp_time_long = None

            batches = None
            batches_size_ind = None
            batches_size_ind_short = None
            batches_size_ind_long = None
            batch_size = None
            buffers_received = None
            buffers_sent = None
            indoubt = None
            channel_status = None
            current_messages = None
            messages = None
            channel_substate = None

            last_message_time = None
            last_message_date = None

            if pymqi.CMQCFC.MQCACH_CHANNEL_NAME in channel_info:

                splunk_event = ""
                index_time = "[" + \
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + \
                    " " + time.strftime("%z") + "] "

                queue_manager_name_str = \
                    "queue_manager=\"%s\" " % queue_manager_name

                host = splunk_host + " "
                process = "mqchs(%i): " % os.getpid()

                channel_name = \
                    channel_info[pymqi.CMQCFC.MQCACH_CHANNEL_NAME].strip()
                logging.debug("Doing channel status for channel [%s]" %
                              channel_name)

                conf_channel_str = ""
                if conf_channel_name != channel_name:
                    conf_channel_str = \
                        "config_channel=\"%s\" " % conf_channel_name

                splunk_event = splunk_event + index_time + host + \
                    process + queue_manager_name_str + conf_channel_str

                splunk_event = splunk_event + "CHANNEL=\"%s\" " % channel_name


                if pymqi.CMQCFC.MQIACH_CHANNEL_STATUS in channel_info:
                    channel_status = \
                        channel_info[pymqi.CMQCFC.MQIACH_CHANNEL_STATUS]

                    if self.textual_values:
                        splunk_event = splunk_event + \
                            "STATUS=\"%s\" " % \
                            self.channel_status_descs[channel_status]
                    else:
                        splunk_event = splunk_event + "STATUS=%d " % \
                                        channel_status

                if pymqi.CMQCFC.MQIACH_CHANNEL_SUBSTATE in channel_info:
                    channel_substate = \
                        channel_info[pymqi.CMQCFC.MQIACH_CHANNEL_SUBSTATE]

                    if self.textual_values:
                        splunk_event = splunk_event + \
                            "SUBSTATE=\"%s\" " % \
                            self.channel_substate_descs[channel_substate]
                    else:
                        splunk_event = splunk_event + \
                            "SUBSTATE=%d " % channel_substate

                if pymqi.CMQC.MQIA_MONITORING_CHANNEL in channel_info:
                    channel_monitoring = \
                        channel_info[pymqi.CMQC.MQIA_MONITORING_CHANNEL]

                    if self.include_zero_values or channel_monitoring > 0:

                        if self.textual_values:
                            splunk_event = splunk_event + \
                                "MONCHL=\"%s\" " % \
                                self.channel_monitoring_descs[channel_monitoring]
                        else:
                            splunk_event = splunk_event + \
                                "MONCHL=%d " % channel_monitoring

                logging.debug("After MONCHL.")

                if pymqi.CMQCFC.MQIACH_BYTES_RCVD in channel_info:
                    bytes_received = \
                        channel_info[pymqi.CMQCFC.MQIACH_BYTES_RCVD]

                    splunk_event = \
                        splunk_event + "BYTSRCVD=%d " % bytes_received

                if pymqi.CMQCFC.MQIACH_BYTES_SENT in channel_info:
                    bytes_sent = channel_info[pymqi.CMQCFC.MQIACH_BYTES_SENT]

                    splunk_event = splunk_event + "BYTSSENT=%d " % bytes_sent

                logging.debug("After BYTSSENT.")

                if pymqi.CMQCFC.MQIACH_BUFFERS_RCVD in channel_info:
                    buffers_received = \
                        channel_info[pymqi.CMQCFC.MQIACH_BUFFERS_RCVD]

                    splunk_event = splunk_event + \
                        "BUFSRCVD=%d " % buffers_received

                if pymqi.CMQCFC.MQIACH_BUFFERS_SENT in channel_info:
                    buffers_sent = \
                        channel_info[pymqi.CMQCFC.MQIACH_BUFFERS_SENT]

                    splunk_event = splunk_event + "BUFSSENT=%d " % buffers_sent

                if pymqi.CMQCFC.MQIACH_BATCHES in channel_info:
                    batches = channel_info[pymqi.CMQCFC.MQIACH_BATCHES]

                    splunk_event = splunk_event + "BATCHES=%d " % batches

                logging.debug("After BATCHES.")
                if pymqi.CMQCFC.MQIACH_BATCH_SIZE in channel_info:
                    batch_size = channel_info[pymqi.CMQCFC.MQIACH_BATCH_SIZE]

                    splunk_event = splunk_event + "BATCHSZ=%d " % batch_size

                if pymqi.CMQCFC.MQIACH_BATCH_SIZE_INDICATOR in channel_info:
                    batches_size_ind = \
                        channel_info[pymqi.CMQCFC.MQIACH_BATCH_SIZE_INDICATOR]

                    if len(batches_size_ind) == 2:
                        batches_size_ind_short = batches_size_ind[0]
                        batches_size_ind_long = batches_size_ind[1]

                        if self.include_zero_values or \
                            (batches_size_ind_short > 0 or
                             batches_size_ind_long > 0):

                            splunk_event = splunk_event + \
                                "XBATCHSZ_SHORT=%d " % batches_size_ind_short
                            splunk_event = splunk_event + \
                                "XBATCHSZ_LONG=%d " % batches_size_ind_long

                logging.debug("After XBATCHSZ.")
                if pymqi.CMQCFC.MQIACH_CURRENT_MSGS in channel_info:
                    current_messages = \
                        channel_info[pymqi.CMQCFC.MQIACH_CURRENT_MSGS]

                    splunk_event = splunk_event + \
                        "CURMSGS=%d " % current_messages

                if pymqi.CMQCFC.MQIACH_MSGS in channel_info:
                    messages = channel_info[pymqi.CMQCFC.MQIACH_MSGS]

                    splunk_event = splunk_event + "MSGS=%d " % messages

                if pymqi.CMQCFC.MQCACH_LAST_MSG_DATE in channel_info:
                    last_message_date = \
                        channel_info[pymqi.CMQCFC.MQCACH_LAST_MSG_DATE]

                    splunk_event = splunk_event + \
                        "LSTMSGDA=\"%s\" " % last_message_date.strip()

                if pymqi.CMQCFC.MQCACH_LAST_MSG_TIME in channel_info:
                    last_message_time = \
                        channel_info[pymqi.CMQCFC.MQCACH_LAST_MSG_TIME]

                    splunk_event = splunk_event + \
                        "LSTMSGTI=\"%s\" " % last_message_time.strip()

                logging.debug("After LSTMSGTI.")
                if pymqi.CMQCFC.MQIACH_NETWORK_TIME_INDICATOR in channel_info:
                    network_time = \
                        channel_info[pymqi.CMQCFC.MQIACH_NETWORK_TIME_INDICATOR]

                    if len(network_time) == 2:
                        network_time_short = network_time[0]
                        network_time_long = network_time[1]

                        if self.include_zero_values or \
                                (network_time_short > 0 or
                                 network_time_long > 0):
                            splunk_event = splunk_event + \
                                "NETTIME_SHORT=%d " % network_time_short
                            splunk_event = splunk_event + \
                                "NETTIME_LONG=%d " % network_time_long

                if pymqi.CMQCFC.MQIACH_XMITQ_TIME_INDICATOR in channel_info:
                    xmitq_time = \
                        channel_info[pymqi.CMQCFC.MQIACH_XMITQ_TIME_INDICATOR]

                    if len(xmitq_time) == 2:
                        xmitq_time_short = xmitq_time[0]
                        xmitq_time_long = xmitq_time[1]

                        if self.include_zero_values or \
                                (xmitq_time_short > 0 or xmitq_time_long > 0):
                            splunk_event = splunk_event + \
                                "XQTIME_SHORT=%d " % xmitq_time_short
                            splunk_event = splunk_event + \
                                "XQTIME_LONG=%d " % xmitq_time_long

                if pymqi.CMQCFC.MQIACH_EXIT_TIME_INDICATOR in channel_info:
                    exit_time = \
                        channel_info[pymqi.CMQCFC.MQIACH_EXIT_TIME_INDICATOR]

                    if len(exit_time) == 2:
                        exit_time_short = exit_time[0]
                        exit_time_long = exit_time[1]

                        if self.include_zero_values or \
                                (exit_time_short > 0 or exit_time_long > 0):
                            splunk_event = splunk_event + \
                                "EXITTIME_SHORT=%d " % exit_time_short
                            splunk_event = splunk_event + \
                                "EXITTIME_LONG=%d " % exit_time_long

                logging.debug("After EXTTIME.")
                if pymqi.CMQCFC.MQIACH_HDR_COMPRESSION in channel_info:
                    comp_header = \
                        channel_info[pymqi.CMQCFC.MQIACH_HDR_COMPRESSION]

                    if len(comp_header) == 2:

                        if self.include_zero_values or \
                                (comp_header[0] > 0 or comp_header[1] > 0):
                            if self.textual_values:
                                comp_header_1 = \
                                    self.channel_compression_descs[comp_header[0]]
                                comp_header_2 = \
                                    self.channel_compression_descs[comp_header[1]]

                                splunk_event = splunk_event + \
                                    "COMPHDR=\"%s,%s\" " % \
                                    (comp_header_1, comp_header_2)
                            else:
                                splunk_event = splunk_event + \
                                    "COMPHDR=%d,%d " % \
                                    (comp_header[0], comp_header[1])

                if pymqi.CMQCFC.MQIACH_MSG_COMPRESSION in channel_info:
                    comp_message = \
                        channel_info[pymqi.CMQCFC.MQIACH_MSG_COMPRESSION]

                    if len(comp_message) == 2:

                        if self.include_zero_values or \
                                (comp_message[0] > 0 or comp_message[1] > 0):
                            if self.textual_values:
                                comp_message_1 = \
                                    self.channel_compression_descs[comp_message[0]]
                                comp_message_2 = \
                                    self.channel_compression_descs[comp_message[1]]

                                splunk_event = splunk_event + \
                                    "COMPMSG=\"%s,%s\" " % \
                                    (comp_message_1, comp_message_2)
                            else:
                                splunk_event = splunk_event + \
                                    "COMPMSG=%d,%d " % \
                                    (comp_message[0], comp_message[1])

                if pymqi.CMQCFC.MQIACH_COMPRESSION_RATE in channel_info:
                    comp_rate = \
                        channel_info[pymqi.CMQCFC.MQIACH_COMPRESSION_RATE]

                    if len(comp_rate) == 2:
                        comp_rate_short = comp_rate[0]
                        comp_rate_long = comp_rate[1]

                        if self.include_zero_values or \
                                (comp_rate_short > 0 or comp_rate_long > 0):
                            splunk_event = splunk_event + \
                                "COMPRATE_SHORT=%d " % comp_rate_short
                            splunk_event = splunk_event + \
                                "COMPRATE_LONG=%d " % comp_rate_long

                if pymqi.CMQCFC.MQIACH_COMPRESSION_TIME in channel_info:
                    comp_time = \
                        channel_info[pymqi.CMQCFC.MQIACH_COMPRESSION_TIME]

                    if len(comp_time) == 2:
                        comp_time_short = comp_time[0]
                        comp_time_long = comp_time[1]

                        if self.include_zero_values or \
                                (comp_time_short > 0 or comp_time_long > 0):
                            splunk_event = splunk_event + \
                                "COMPTIME_SHORT=%d " % comp_time_short
                            splunk_event = splunk_event + \
                                "COMPTIME_LONG=%d " % comp_time_long

                if pymqi.CMQCFC.MQIACH_IN_DOUBT in channel_info:
                    indoubt = channel_info[pymqi.CMQCFC.MQIACH_IN_DOUBT]

                    if self.include_zero_values or indoubt > 0:
                        if self.textual_values:
                            indoubt_desc = 0
                            if indoubt > 0:
                                indoubt_desc = "YES"
                            else:
                                indoubt_desc = "NO"

                            splunk_event = splunk_event + \
                                "INDOUBT=\"%s\" " % indoubt_desc
                        else:
                            splunk_event = splunk_event + \
                                "INDOUBT=%d " % indoubt

                logging.debug("After INDOUBT.")

                print_xml_single_instance_mode(splunk_host, splunk_event)


class ErrorQueueResponseHandler(object):
    """
    Custom XML Error message format.

    """
    def __init__(self,**args):

        self.args = args
        self.mqmd_dicts = None

        self.include_mqmd = False
        if "include_mqmd" in self.args:
            if self.args["include_mqmd"].lower().strip() == "true":
                self.include_mqmd = True
            else:
                self.include_mqmd = False
        else:
            self.include_mqmd = False

        self.pretty_mqmd = False
        if "pretty_mqmd" in self.args:
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

        self.include_blob = False
        if "include_blob" in self.args:
            if self.args["include_blob"].lower().strip() == "true":
                self.include_blob = True
            else:
                self.include_blob = False
        else:
            self.include_blob = False

        self.extract_elements = True
        if "extract_elements" in self.args:
            if self.args["extract_elements"].lower().strip() == "false":
                self.extract_elements = False
            else:
                self.extract_elements = True
        else:
            self.extract_elements = True

        self.extract_message_header = True
        if "extract_message_header" in self.args:
            if self.args["extract_message_header"].lower().strip() == "false":
                self.extract_message_header = False
            else:
                self.extract_message_header = True
        else:
            self.extract_message_header = True

        self.filter_text_elements = True
        if "filter_text_elements" in self.args:
            if self.args["filter_text_elements"].lower().strip() == "false":
                self.filter_text_elements = False
            else:
                self.filter_text_elements = True
        else:
            self.filter_text_elements = True

        self.use_mqmd_puttime = True
        if "use_mqmd_puttime" in self.args:
            if self.args["use_mqmd_puttime"].lower().strip() == "false":
                self.use_mqmd_puttime = False
            else:
                self.use_mqmd_puttime = True
        else:
            self.use_mqmd_puttime = True

        self.blob_limit = 65536
        if "blob_limit" in self.args:
            try:
                self.blob_limit = int(self.args["blob_limit"].strip())
            except:
                self.blob_limit = 65536
        else:
            self.blob_limit = 65536

        self.make_mqmd_printable = False
        if "make_mqmd_printable" in self.args:
            self.make_mqmd_printable = self.args["make_mqmd_printable"].lower().strip()
        else:
            self.make_mqmd_printable = False

        self.write_messages = True
        if "write_messages" in self.args:
            if self.args["write_messages"].lower().strip() == "false":
                self.write_messages = False
            else:
                self.write_messages = True
        else:
            self.write_messages = True

        self.gzip_messages = True
        if "gzip_messages" in self.args:
            if self.args["gzip_messages"].lower().strip() == "false":
                self.gzip_messages = False
            else:
                self.gzip_messages = True
        else:
            self.gzip_messages = True

        self.write_messages_folder = "/opt/splunk/esb/brokererrors/"
        if "write_messages_folder" in self.args:
            self.write_messages_folder = self.args["write_messages_folder"]


    def extract_values(self, msg_data, tag_name, first_only=False, reverse=False):
        done = False
        start_pos = 0
        end_pos = 0
        #value = ""
        start_tag = "<%s>" % tag_name
        end_tag = "</%s>" % tag_name
        values = []
        while not done:

            start_pos = msg_data.find(start_tag, start_pos)
            if start_pos >= 0:
                end_pos = msg_data.find(end_tag, start_pos + 1)
                if end_pos > 0:
                    #value = value + msg_data[start_pos + len(start_tag):end_pos] + "|"
                    if reverse:
                        values = [msg_data[start_pos + len(start_tag):end_pos]] + values
                    else:
                        values.append(msg_data[start_pos + len(start_tag):end_pos])

                    if first_only:
                        done = True
                    start_pos = end_pos
                else:
                    logging.error("End tag expected. TagName: %s MsgData: %s " % (str(tag_name), str(msg_data)[0:100]))
                    start_pos = start_pos + 1
            else:
                done = True

        return values

    def __call__(self, splunk_host, queue_manager_name, queue, msg_data, msg_desc, from_trigger, **kw):

        splunk_event = ""
        logging.debug("ErrorQueueResponseHandler in  __call__()")
        queue_manager_name_str = " queue_manager=%s" % queue_manager_name
        queue_str = " queue=%s" % queue
        host = " " + splunk_host
        process = " mqinput(%i):" % os.getpid()
        msg_id = " message_id=%s" % binascii.hexlify(msg_desc["MsgId"])
        message_file_name = ""


        mqmd_str = ""
        if self.include_mqmd and (msg_desc is not None):
            new_mqmd = make_mqmd(msg_desc, self.mqmd_dicts, self.pretty_mqmd, self.make_mqmd_printable)
            for (mqmd_key, mqmd_value) in list(new_mqmd.items()):
                if isinstance(mqmd_value, int) or isinstance(mqmd_value, float) or str(mqmd_value).startswith("MQ"):
                    mqmd_str = mqmd_str + " %s=%s" % (str(mqmd_key).strip(), str(mqmd_value))
                else:
                    mqmd_str = mqmd_str + ' %s="%s"' % (str(mqmd_key).strip(), str(mqmd_value))

        index_time_o = datetime.datetime.now()
        index_time = "[" + index_time_o.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + time.strftime("%z") + "]"
        if self.use_mqmd_puttime:
            puttime = datetime.datetime.strptime(msg_desc["PutDate"] + " " + msg_desc["PutTime"][0:6], "%Y%m%d %H%M%S")

            index_time_o = puttime - datetime.timedelta(seconds=time.timezone)

            h_secs = msg_desc["PutTime"][6:]
            index_time = "[" + index_time_o.strftime("%Y-%m-%d %H:%M:%S") + "." + h_secs + "0 " +  time.strftime("%z") + "]"


        if self.write_messages:
            try:
                date_s = time.strftime("%Y%m%d")
                cur_folder = os.path.join(os.path.join(os.path.join(self.write_messages_folder, queue_manager_name), queue), date_s)

                if not os.path.exists(cur_folder):
                    os.makedirs(cur_folder)

                file_name = "ErrorMessage_" +  binascii.hexlify(msg_desc["MsgId"]) + ".xml"
                full_file_name = os.path.join(cur_folder, file_name)
                if self.gzip_messages:
                    f = gzip.open(full_file_name + ".gz", 'wb')
                    f.write(msg_data)
                    f.close()
                else:
                    f = open(full_file_name, "w")
                    f.write(msg_data)
                    f.close()
                message_file_name = ' message_file_name="%s"'  % full_file_name
            except Exception as ex:
                logging.error("Failed to write error message. " + str(ex))

        new_msg_data = ""

        blob_start = msg_data.find("<BLOB>")
        blob_end = msg_data.find("</BLOB>", blob_start)

        blob_len = blob_end - blob_start + 6

        if self.include_blob:
            mod_blob_limit = self.blob_limit % 2

            if mod_blob_limit > 0:
                self.blob_limit = self.blob_limit + 1

                if self.blob_limit > blob_len:
                    self.blob_limit = blob_len

            new_msg_data = msg_data[:blob_start + 6 + self.blob_limit] + msg_data[blob_end:]

        else:
            new_msg_data = msg_data[:blob_start + 6] + msg_data[blob_end:]



        #logging.debug("extract elements?")
        if self.extract_elements:
            #logging.debug("Extracting elements.")
            #extract main fields via substring instead of xpath

            try:

                timestamp = ""
                nl = self.extract_values(new_msg_data, "Timestamp", first_only=True)
                if len(nl) > 0:
                    timestamp = ' error_timestamp="%s"' % nl[0]

                broker = ""
                nl = self.extract_values(new_msg_data,"BrokerName", first_only=True)
                if len(nl) > 0:
                    broker = ' broker="%s"' % nl[0]
                #logging.debug("extracted brokername")
                eg = ""
                nl = self.extract_values(new_msg_data,"ExecutionGroupName",first_only=True)
                if len(nl) > 0:
                    eg = ' execution_group="%s"' % nl[0]

                flow = ""
                nl = self.extract_values(new_msg_data,"MessageFlowLabel",first_only=True)
                if len(nl) > 0:
                    flow = ' flow="%s"' % nl[0]


                source_q = ""
                nl = self.extract_values(new_msg_data,"SourceQueue",first_only=True)
                if len(nl) > 0:
                    source_q = ' source_queue="%s"' % nl[0]

                r2_q = ""
                nl = self.extract_values(new_msg_data,"ReplyToQ",first_only=True)
                if len(nl) > 0:
                    r2_q = ' replyto_queue="%s"' % nl[0]
                #logging.debug("extracted r2q")
                r2_proto = ""
                nl = self.extract_values(new_msg_data,"ReplyProtocol",first_only=True)
                if len(nl) > 0:
                    r2_proto = ' reply_protocol="%s"' % nl[0]

                msg_fmt = ""
                nl = self.extract_values(new_msg_data,"MessageFormat",first_only=True)
                if len(nl) > 0:
                    msg_fmt = ' message_format="%s"' % nl[0]

                msg_ccsid = ""
                nl = self.extract_values(new_msg_data,"CodedCharSetId",first_only=True)
                if len(nl) > 0:
                    msg_ccsid = ' message_ccsid="%s"' % nl[0]

                msg_hdr = ""
                if self.extract_message_header:
                    nl = self.extract_values(new_msg_data,"MessageHeader",first_only=True)
                    if len(nl) > 0:
                        msg_hdr = ' message_header="<MessageHeader>%s</MessageHeader>"' % nl[0].replace('"', "'")


                #logging.debug("extracting messagetext")
                message_texts = ""
                nl = self.extract_values(new_msg_data,"MessageText",first_only=False)

                temp_msg_txt = ""
                if len(nl) > 0:
                    #message_texts = " message_text="
                    for n in nl:
                        temp_msg_txt = temp_msg_txt + n.replace('"', "'").replace("||", "+") + "|"
                        #temp_msg_txt = temp_msg_txt + ' message_text="%s"' % n.text.replace('"', "'")
                    if temp_msg_txt[-1:] == "|":
                        temp_msg_txt = temp_msg_txt[:-1]

                    if temp_msg_txt[0:1] == "|":
                        temp_msg_txt = temp_msg_txt[1:]

                    message_texts = ' message_text="%s"' % temp_msg_txt
                    #message_texts = temp_msg_txt



                txt_elements = ""
                nl = self.extract_values(new_msg_data,"Text", first_only=False)
                if len(nl) > 0:
                    #txt_elements = " text_elements="
                    tmp_el = ""
                    for n in nl:
                        if self.filter_text_elements:

                            try:
                                dummy_float = float(n)
                            except:
                                if n.find("rethrowing") <= 0:
                                    tmp_el = n.replace('"', "'").replace("||", "+").replace("|", "+") + "|" + tmp_el
                                    #tmp_el = ' exception_text="%s"' % n.text.replace('"', "'") + tmp_el

                    if tmp_el[-1:] == "|":
                        tmp_el = tmp_el[:-1]

                    if tmp_el[0:1] == "|":
                        tmp_el = tmp_el[1:]

                    txt_elements = ' exception_text="%s"' % tmp_el
                    #txt_elements = tmp_el
                payload = timestamp + broker + eg + flow + source_q + r2_q + r2_proto + msg_fmt + msg_ccsid + msg_hdr + message_texts + txt_elements

            except Exception as ex:
                logging.error("XML parsing error.  Including whole message." + str(ex))
                payload = ' xmlparsingfail="true" payload="%s"' %  new_msg_data
        else:

            payload = ' extractfields="false" payload="%s"' %  new_msg_data

        #handle trigger
        if from_trigger:
            pass
        else:
            splunk_event = splunk_event + index_time + host + process + queue_manager_name_str +  queue_str + msg_id + message_file_name +  mqmd_str + payload
            print_xml_single_instance_mode(splunk_host, splunk_event)
