#!/opt/splunk/bin/python
'''
IBM Websphere MQ Modular Input for Splunk
Hannes Wagener - 2015

This is a custom search command to fetch a payload 
previously written to disk by a response handler.

DISCLAIMER
You are free to use this code in any way you like, subject to the
Python & IBM disclaimers & copyrights. I make no representations
about the suitability of this software for any purpose. It is
provided "AS-IS" without warranty of any kind, either express or
implied.

'''
from __future__ import print_function

import csv
import sys
import splunk.Intersplunk
import string
import os
import gzip
import binascii
import zlib
import base64


MONGO_SUPPORTED = False
try:
    import pymongo
    import bson
    MONGO_SUPPORTED = True
except:
    pass
    

MONGODB_HOST = "127.0.0.1"
MONGODB_PORT = 27017
MONGODB_DB_NAME = "brkerrs"
MONGODB_USER = "splunk"
MONGODB_PASSWORD = "splunk"
MONGODB_AUTH_DB = "admin"
MONGODB_USE_AUTH = False

mongodb_client = None
mongodb_db = None

(isgetinfo, sys.argv) = splunk.Intersplunk.isGetInfo(sys.argv)

if isgetinfo:
    splunk.Intersplunk.outputInfo(True, False, True, False, None, True)

if len(sys.argv) > 4:
    splunk.Intersplunk.parseError("Too many arguments provided.")


valid_parms = ["excludeevent", "includebitstream", "extractbitstream", "decodebitstream", "convertbitstream"]

i = 1
parm_dict = {}
while i < len(sys.argv):
    arg = sys.argv[i]

    if arg.count("=") == 1:
        (parm, value) = arg.split("=")
        if parm not in valid_parms:
            splunk.Intersplunk.parseError("Invalid argument. Valid options are includebitstream/extractbitstream/decodebitstream/convertbitstream=<true|false>")

        if parm == "includebitstream" or parm == "convertbitstream" or parm == "decodebitstream" or parm == "extractbitstream" or parm == "exludeevent":
            if value.strip().lower() != "true" and value.strip().lower() != "false":
                splunk.Intersplunk.parseError("Invalid argument value for excludeevent or includebitstream or extractbitstream or decodebitstream or convertbitstream. ")

        parm_dict[parm] = value

    else:
        if arg.count("=") > 1 or arg.count("=") <= 0:
            splunk.Intersplunk.parseError("Invalid argument. Valid options are includebitstream/extractbitstream/decodebitstream/convertbitstream=<true|false>")

    i = i + 1
    # outputInfo automatically calls sys.exit()

#print "after outputinfo"

results = splunk.Intersplunk.readResults(None, None, True)
messages = {}

def isPrintable(char):
    '''Return true if the character char is printable or false if it is not printable.
    '''
    if string.printable.count(char) > 0:
        return True
    else:
        return False

def makePrintable(instr):
    '''Return a printable representation of the string instr.
    '''
    retstr = ''
    for char in instr:
        if not isPrintable(char):
            retstr = retstr + '.'
        else:
            retstr = retstr + char
    return retstr

def get_msg_from_mongodb(mongodb_db, mongodb_collection, msg_id):

    if mongodb_db is None:
        #sys.stderr.write("Mongodb db none?")
        return None

    if msg_id is None:
        return None
    else:
        if len(msg_id) != 24:
            #splunk.Intersplunk.addWarnMessage(messages, "Msg id not 24 bytes?: %s" % (str(msg_id)))
            return None

    try:

        msg_doc = mongodb_db[mongodb_collection].find_one({"_id": bson.objectid.ObjectId(msg_id)})

        if msg_doc is not None:
            msg_data = msg_doc["msg_data"]

            uncomp_msg_data = zlib.decompress(base64.decodestring(msg_data))
            return uncomp_msg_data

    except Exception as ex:
        sys.stderr.write("Exception while fetching message. Exception: %s\n" % (str(ex)))
        #splunk.Intersplunk.addMessage(messages, "Exception while fetching message from mongodb message. Exception: %s" % (str(ex)))
        pass

    return None

for res in results:

    try:
        msg_data = ""
        if "event_file_name" in res:

            if os.path.exists(res["event_file_name"]):
                msg_file = open(res["event_file_name"], "r")
                msg_data = msg_file.read()
                msg_file.close()

            else:
                if os.path.exists(res["event_file_name"] + ".gz"):
                    msg_file = gzip.open(res["event_file_name"] + ".gz", "rb")
                    msg_data = msg_file.read()
                    msg_file.close()

        if "collection" in res and "mongoid" in res:
            if mongodb_client is None:
                mongodb_client = pymongo.MongoClient(MONGODB_HOST, MONGODB_PORT)
                mongodb_db = mongodb_client[MONGODB_DB_NAME]
                if MONGODB_USE_AUTH:
                    mongodb_db.authenticate(MONGODB_USER, MONGODB_PASSWORD, source=MONGODB_AUTH_DB)

            msg_data = get_msg_from_mongodb(mongodb_db, res["collection"], res["mongoid"])

        if msg_data != "" and msg_data is not None:

            exclude_event = False
            include_bitstream = False
            extract_bitstream = False
            convert_bitstream = False
            decode_bitstream = False

            if "excludeevent" in parm_dict:
                if parm_dict["excludeevent"].lower() == "true":
                    exclude_event = True
                else:
                    exclude_event = False

            if "includebitstream" in parm_dict:
                if parm_dict["includebitstream"].lower() == "true":
                    include_bitstream = True
                else:
                    include_bitstream = False

            if "extractbitstream" in parm_dict:
                if parm_dict["extractbitstream"].lower() == "true":
                    extract_bitstream = True
                else:
                    extract_bitstream = False

            if "convertbitstream" in parm_dict:
                if parm_dict["convertbitstream"].lower() == "true":
                    convert_bitstream = True
                else:
                    convert_bitstream = False

            if "decodebitstream" in parm_dict:
                if parm_dict["decodebitstream"].lower() == "true":
                    decode_bitstream = True
                else:
                    decode_bitstream = False

            bs_tag_start = msg_data.find("<wmb:bitstream ")
            bs_start = 0
            bs_end = 0
            if bs_tag_start > 0:
                bs_start = msg_data.find(">", bs_tag_start + 1)

            if bs_start > 0:
                bs_end = msg_data.find("</wmb:bitstream>", bs_start)

            if bs_start > 0 and bs_end > 0:
                bs_len = bs_end - bs_start + 1

                new_msg_data = ""
                if include_bitstream:
                    new_msg_data = msg_data
                else:
                    new_msg_data = msg_data[:bs_start + 1] + msg_data[bs_end:]

                if extract_bitstream:
                    bitstream = msg_data[bs_start + 1: bs_end]

                    if decode_bitstream:
                        enc = ""
                        dc_bs = ""
                        enc_start = msg_data.find('wmb:encoding="', bs_tag_start)
                        if enc_start > 0:
                            enc_end = msg_data.find('"', enc_start + 15)
                            if enc_end > 0:
                                enc = msg_data[enc_start + 14:enc_end]

                                if enc == "base64Binary":
                                    dc_bs = base64.decodestring(bitstream)
                                else:
                                    if enc == "hexBinary":
                                        dc_bs = binascii.unhexlify(bitstream)


                        if dc_bs != "":
                            bitstream = dc_bs
                            if convert_bitstream:
                                ccsid = 1208
                                if "message_ccsid" in res:
                                    try:
                                        ccsid = int(res["message_ccsid"])
                                    except:
                                        ccsid = 1208
                                else:
                                    if "bitstreamccsid" in parm_dict:
                                        try:
                                            ccsid = int(parm_dict["bitstreamccsid"])
                                        except:
                                            ccsid = 1208

                                if ccsid == 500 or ccsid == 37:
                                    if ccsid == 500:
                                        bitstream = dc_bs.decode("cp500")
                                    else:
                                        bitstream = dc_bs.decode("cp037")

                                bitstream = makePrintable(bitstream)

                    res["bitstream"] = bitstream
            else:
                new_msg_data = msg_data

            if not exclude_event:
                res["event"] = new_msg_data

    except Exception as ex:
        splunk.Intersplunk.addErrorMessage(messages, "Exception occurred.  " + str(ex))

splunk.Intersplunk.outputResults(results, messages=messages)




