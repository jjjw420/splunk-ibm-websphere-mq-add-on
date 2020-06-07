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
import base64
import zlib

MONGO_SUPPORTED = False
try:
    import pymongo
    import bson
    MONGO_SUPPORTED = True
except:
    pass
    

MONGODB_HOST = "127.0.0.1"
MONGODB_PORT = 27017
MONGODB_DB_NAME = ""
MONGODB_USER = ""
MONGODB_PASSWORD = ""
MONGODB_AUTH_DB = ""
MONGODB_USE_AUTH = False


mongodb_client = None
mongodb_db = None

(isgetinfo, sys.argv) = splunk.Intersplunk.isGetInfo(sys.argv)

if isgetinfo:
    splunk.Intersplunk.outputInfo(True, False, True, False, None, True)

if len(sys.argv) > 7:
    splunk.Intersplunk.parseError("Too many arguments provided.")


valid_parms = ["includeblob", "bloblimit", "dontfixpdgheader", "extractblob", "excludepayload", "convertblob", "extractbloblimit"]

i = 1
parm_dict = {}
while i < len(sys.argv):
    arg = sys.argv[i]

    if arg.count("=") == 1:
        (parm, value) = arg.split("=")
        if parm not in valid_parms:
            splunk.Intersplunk.parseError("Invalid argument. Valid options are includeblob/dontfixpdgheader/extractblob/excludepayload/convertblob=<true|false> bloblimit/extractbloblimit=<integer>")

        if parm == "bloblimit" or parm == "extractbloblimit":
            try:
                int(value.strip())
            except:
                splunk.Intersplunk.parseError("Invalid argument vale for bloblimit or extractbloblimit.  Must be an integer value.")

        if parm == "includeblob" or parm == "dontfixpdgheader" or parm == "extractblob" or parm == "excludepayload" or parm == "convertblob":
            if value.strip().lower() != "true" and value.strip().lower() != "false":
                splunk.Intersplunk.parseError("Invalid argument value for includeblob, extractblob or dontfixpdg.  Must be either true or false")

        parm_dict[parm] = value

    else:
        if arg.count("=") > 1 or arg.count("=") <= 0:
            splunk.Intersplunk.parseError("Invalid argument. Valid options are includeblob/dontfixpdgheader/extractblob/excludepayload/convertblob=<true|false> bloblimit/extractbloblimit=<integer>")

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
        uncomp_msg_data = ""

        if msg_doc is not None:
            if "msg_data" in msg_doc:
                msg_data = msg_doc["msg_data"]

                #uncomp_msg_data = zlib.decompress(base64.decodestring(msg_data), -15)
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
        if "message_file_name" in res:

            if os.path.exists(res["message_file_name"]):
                msg_file = open(res["message_file_name"], "r")
                msg_data = msg_file.read()
                msg_file.close()

            else:
                if os.path.exists(res["message_file_name"] + ".gz"):
                    msg_file = gzip.open(res["message_file_name"] + ".gz", "rb")
                    msg_data = msg_file.read()
                    msg_file.close()

        if "collection" in res and "mongoid" in res:
            if mongodb_client is None:
                mongodb_client = pymongo.MongoClient(MONGODB_HOST, MONGODB_PORT)
                mongodb_db = mongodb_client[MONGODB_DB_NAME]
                if MONGODB_USE_AUTH:
                    mongodb_db.authenticate(MONGODB_USER, MONGODB_PASSWORD, source=MONGODB_AUTH_DB)

            msg_data = get_msg_from_mongodb(mongodb_db, res["collection"], res["mongoid"])

        if msg_data != "":

            blob_start = msg_data.find("<BLOB>")
            blob_end = msg_data.find("</BLOB>", blob_start)

            blob_len = blob_end - blob_start + 6

            include_blob = False
            blob_limit = 0

            if "includeblob" in parm_dict:
                if parm_dict["includeblob"].lower() == "true":
                    include_blob = True
                else:
                    include_blob = False

            if "bloblimit" in parm_dict:
                blob_limit = int(parm_dict["bloblimit"])

            if blob_limit == 0:
                blob_limit = blob_len

            new_msg_data = ""
            if include_blob:
                mod_blob_limit = blob_limit % 2

                if mod_blob_limit > 0:
                    blob_limit = blob_limit + 1

                    if blob_limit > blob_len:
                        blob_limit = blob_len

                new_msg_data = msg_data[:blob_start + 6 + blob_limit] + msg_data[blob_end:]

            else:
                new_msg_data = msg_data[:blob_start + 6] + msg_data[blob_end:]


            fix_pdg = True
            if "dontfixpdgheader" in parm_dict:
                if parm_dict["dontfixpdgheader"].lower() == "true":
                    fix_pdg = True
                else:
                    fix_pdg = False

            if fix_pdg:
                done = False
                while not done:
                    xsi_start = new_msg_data.find("<xmlns:xsi>")
                    if xsi_start > 0:
                        xsi_end = new_msg_data.find("</xmlns:xsi>")
                        if xsi_end > 0:
                            new_msg_data = new_msg_data[:xsi_start] + new_msg_data[xsi_end + 12:]
                        else:
                            splunk.Intersplunk.addWarnMessage(messages, "Weird.  No close tag for pdg xmlns xsi issue.")
                    else:
                        done = True

            excludepayload = False
            if "excludepayload" in parm_dict:
                if parm_dict["excludepayload"].lower() == "true":
                    excludepayload = True
                else:
                    excludepayload = False

            if not excludepayload:
                res["payload"] = new_msg_data

            extractblob = False
            extractbloblimit = 0

            if "extractblob" in parm_dict:
                extractblob = bool(parm_dict["extractblob"])

            if "extractbloblimit" in parm_dict:
                extractbloblimit = int(parm_dict["extractbloblimit"])

            if extractbloblimit == 0:
                extractbloblimit = blob_len

            mod_blob_limit = extractbloblimit % 2

            if mod_blob_limit > 0:
                extractbloblimit = extractbloblimit + 1

                if extractbloblimit > blob_len:
                    extractbloblimit = blob_len


            if extractblob:
                blob = msg_data[blob_start + 6: blob_end]
                blob = blob[0:extractbloblimit]

                convertblob = False
                if "convertblob" in parm_dict:
                    if parm_dict["convertblob"].lower() == "true":
                        convertblob = True
                    else:
                        convertblob = False


                if convertblob:
                    try:
                        extractbloblimit = extractbloblimit * 2
                        if extractbloblimit > blob_len:
                            extractbloblimit = blob_len

                        blob = msg_data[blob_start + 6: blob_end]
                        blob = blob[0:extractbloblimit]
                        blob = binascii.unhexlify(blob)

                        ccsid = 1208
                        if "message_ccsid" in res:
                            try:
                                ccsid = int(res["message_ccsid"])
                            except:
                                ccsid = 1208

                        if ccsid == 500 or ccsid == 37:
                            if ccsid == 500:
                                blob = blob.decode("cp500")

                            else:
                                blob = blob.decode("cp037")

                        blob = makePrintable(blob)
                    except Exception as ex:
                        sys.stderr.write("Exception occurred while converting BLOB.  Exception: %s \n" % str(ex))

                res["blob"] = blob



    except Exception as ex:
        splunk.Intersplunk.addErrorMessage(messages, "Exception occurred.  " + str(ex))


splunk.Intersplunk.outputResults(results, messages=messages)
