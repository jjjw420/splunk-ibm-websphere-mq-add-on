# splunk-ibm-websphere-mq-add-on - TA-mq

By Hannes Wagener - 2015 

## Overview

This is a Splunk modular input add-on for IBM Websphere MQ.
Currently two data inputs are supported.  One for creating events from messages on IBM Websphere queues and another for channel status statistics.

Created from the Splunk modular input examples.

## Features

* Simple UI based configuration via Splunk Manager
* Poll  IBM Websphere MQ queues for messages at interval or can be triggered from the Websphere MQ trigger monitor(future feature).
* Poll IBM Websphere MQ Channel Status statistics.
* Uses regular splunk sourcetypes for the events ("Generic single line" or "syslog") 
* You can specify multiple queues or channels per data input.  You can specify whether to use a thread per data input or per queue/channel.
* Automatic thread management.  No need to restart splunk after changes are made to a data input.  This includes adding and removing queues.
* Includes default response handlers for queue input and channel status input.
* Includes a response handler for IBM Websphere Message Broker monitoring events.

## Dependencies

* Splunk 6.0+, 7+, 8+
* PyMQI 1.5+
* ctypes library for Python.  **NOTE: Splunk V8 has the ctypes libary installed by default for both Python2 and Python3.  See the dedicated section in the Troubleshooting section on where you can find or build a compatible _ctypes.so**  
* IBM Websphere MQ Client Libraries V7+
* Only currently supported on Linux (but Windows (and any other platform) should be possible if the platform versions of the PyMQI and ctypes libraries are installed) 

## Setup

**IMPORTANT:  The plgin folder has been renamed from "mq_ta" to "TA-mq".   MAke sure that you take this into account if you are upgrading the plugin.

### Installation
* Install the IBM Websphere MQ client.  Ensure that the user that runs splunk has access to the MQ client libraries.  The easiest way to achieve this is to add the MQ client library locations (generaly /opt/mqm/lib) to the dynamic loader configuration (ld.so.conf). 
* Get and build the PyMQI library.  You can download from here: https://github.com/dsuch/pymqi 
* Untar the MQ modular input release to your $SPLUNK_HOME/etc/apps directory.
* Copy the built PyMQI library to the $SPLUNK_HOME/etc/apps/TA-mq/bin folder.
* Copy python c_types library directory to the $SPLUNK_HOME/etc/apps/TA-mq/bin directory.  Splunk's Python interpreter is built with UCS-2.  Make sure you use a compatible _ctypes.so library.  **NOTE:  This step is not required if running Splunk V8+as the ctypes library is included for both Python2 and Python3.**  
* Ensure that the pymqi and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Restart Splunk

### Upgrade
* Take a backup of your installation.   The  $SPLUNK_HOME/etc/apps directory is very important to backup.
* Untar the MQ modular input release to your $SPLUNK_HOME/etc/apps directory.  
* If you still have the $SPLUNK_HOME/etc/apps/mq_ta directory make sure you migrate all your "local" splunk config to the new $SPLUNK_HOME/etc/apps/TA-mq directory.  Delete the old $SPLUNK_HOME/etc/apps/mq_ta directory(do not rename it - delete it).
* Restart your Splunk instance.


## Response Handlers

Even though the included response handlers works very well, you are encouraged to create your own
response handlers to handle a specific type or format of MQ message.  Every site that has IBM MQ will 
have custom formats for mesages and which will be written in a variety of different codepages 
depending on the platform.  
By creating your own response handler you can parse your specific MQ message and index the event in 
Splunk so that it's attributes are accessible for searches.  Let the included response handlers 
serve as examples to your own.

### DefaultQueueResponseHandler
* Basic handler for MQ messages.
* Supported options: 
   * `include_payload=false/true` - Include the message payload in the event.  Default: true
   * `use_mqmd_puttime=false/true` - Use the message put time as the event time.  Default: true 
   * `include_mqmd=false/true` - Include the MQMD in the event.  Default: false 
   * `pretty_mqmd=false/true` - Use textual descriptions for MQMD values. Default: true
   * `make_mqmd_printable=false/true` - Escape non text values in the MQMD.  Default: true 
   * `payload_limit=1024` - How many bytes of the payload to include in the splunk event.  Default: 1024 (1kb)  
   * `encode_payload=false/base64/hexbinary` - Encode the payload.   Default: false 
   * `make_payload_printable=false/true` - Escape non text values in the payload.  Default: true
   * `log_payload_as_event=false/true` - If false do not log the payload as a name/value pair.  Default: false
   * `payload_quote_char='/"` - Use a specific character to quote the "payload" kv value. Default: " (double quote)

### DefaultChannelStatusResponseHandler
* Default handler for Channel Status Statistics.
* Supported options:
  * `include_zero_values=true/false` - Include values that are set to zero or default values in the event.  Default: false
  * `textual_values=true/false` - Include the textual description for channel status parameters.  Default: true

### BrokerEventResponseHandler
* IBM Message Broker Monitoring event handler.   
* Parses a Message Broker monitoring event and extracts the required fields.  
* Supported options:
  * `include_complex_top_level = true/false` - Include the complex type top level element when logged.
  * `include_bitstream = true/false` - Include the bitstream (base64 or blob) in the splunk event.
  * `write_events = true/false` - Write out the events to disk.  NOTE:  Splunk must have access to the folder to which the events will be written to.
  * `gzip_events = true/false` - Gzip the events written to disk.
  * `write_events_folder =folder` - Folder to which events must be written to.  NOTE:  Splunk must have access to the folder to which the events will be written to.  

## Logging

Any modular input log errors will get written to $SPLUNK_HOME/var/log/splunk/splunkd.log.  Debug logging can be "enabled by changing the "ExecProcessor" property under "Server logging" to DEBUG.

## Troubleshooting

* You are using Splunk 6+
* Look for any errors in $SPLUNK_HOME/var/log/splunk/splunkd.log
* Enable debug logging by changing the "ExecProcessor" property under "Server logging" to DEBUG.  This will output some debug at various places in the code.  
Search for the following in Splunk: `index=_internal component=ExecProcessor TA-mq`
* Ensure that the PyMQI and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Ensure that the IBM Websphere MQ libraries are available to the user which runs Splunk. 

### How to find a Splunk Python2 compatible "_ctypes.so" (pre Splunk V8)
The number one problem most people experience with the installation is finding a compatible ctypes library for Splunk's Python2 interpreter(particulary _ctypes.so).  

Splunk's Python2 interpreter was built using UCS2 whereas most of the recent builds on Ubuntu, CentOS, RHEL, etc. is built using UCS4 making the two incompatible.  Splunk V8 comes with the ctypes library installed for both the Python2 and Python3 interpreters by default making the installation much simpler.  But earlier versions of Splunk does not include a ctypes library by default.

#### Determining what type of _ctypes.so you require.
The easiest way to see whether a Python interpreter was built using UCS2 or UCS4 is to check the `sys.maxunicode` value.  
For a UCS2 build the value returned will be 65535.  On a UCS4 build the value returned will be 1114111.  

For instance - running the python2 interpreter that comes with Splunk:
<pre>    
  $ /opt/splunk/bin/python2
  Python 2.7.15 (default, Jun 24 2019, 17:39:18)
  [GCC 5.3.0] on linux2
  Type "help", "copyright", "credits" or "license" for more information.
  >>> import sys
  >>> print sys.maxunicode
  65535
  >>>
</pre>
    
The 65535 value means that Splunk's Python2 interpreter was built using UCS2.

#### Determining if an existing _ctypes.so was built using UCS2 or UCS4
The quickest way to determine if a _ctypes.so was built using UCS2 or UCS4 is to simply print the enclosed strings and searching for "UCS".  

For instance - a _ctypes bullt using UCS4(incompatble with Splunk's Python2) will have the following output:  
<pre>
  $ strings _ctypes.so | grep UCS
  PyUnicodeUCS4_AsWideChar
  PyUnicodeUCS4_FromEncodedObject
  PyUnicodeUCS4_FromWideChar
  PyUnicodeUCS4_AsEncodedString
  PyUnicodeUCS4_FromUnicode
</pre>
A version that will be compatible with Splunk's Python2 will have output that looks as follows:
<pre>
  $ strings lib-dynload/_ctypes.so  | grep UCS
  PyUnicodeUCS2_AsWideChar
  PyUnicodeUCS2_FromEncodedObject
  PyUnicodeUCS2_FromWideChar
  PyUnicodeUCS2_AsEncodedString
  PyUnicodeUCS2_FromUnicode
  PyUnicodeUCS2_FromWideChar
  PyUnicodeUCS2_FromUnicode
  PyUnicodeUCS2_FromEncodedObject
  PyUnicodeUCS2_AsWideChar
  PyUnicodeUCS2_AsEncodedString
  PyUnicodeUCS2_AsWideChar
  PyUnicodeUCS2_FromEncodedObject
  PyUnicodeUCS2_FromWideChar
  PyUnicodeUCS2_AsEncodedString
  PyUnicodeUCS2_FromUnicode
</pre>
**NOTE: If no strings containing "UCS" was found the library is NOT compatible and almost certainly a Python3 version that cannot be used with Python2.**   

#### Where to find a compatible _ctypes.so
* Upgrade to Splunk V8.  All you will require is the pymqi library as Splunk V8 comes with the ctypes library pre-installed.
* The ctypes library that comes with Splunk V8 is compatible with earlier versions of Splunk (Only verified on Splunk 7.1+ - however technically it should work on any Splunk Python2 that is built using UCS2). 
* Build your own on your own platform!   If you download the Python2 source code you can build your own "UCS2" Python2 (and the subsequent _ctypes.so) by setting the "--enable-unicode=ucs2" option on the "configure" step.  eg.
`./configure --enable-unicode=ucs2`
* Some users have commented that on Ubuntu some of the "Steam" apps contain a compatible _ctypes.so.  This is unconfirmed and seems to be version and app dependent.  I found a few _ctypes.so libraries on on my system (Ubuntu 18.04) however all of them was built using UCS4 instead of the required UCS2.
* Send me an email and I can help you find or build one for your platform.   I do not like sending prebuilt libraries about as there are implications (eg. security, compatibility, etc.) I prefer not to be involved with as a 3rd party.  I prefer you help yourself!


## DISCLAIMER
You are free to use this code in any way you like, subject to the Python & IBM disclaimers & copyrights. I make no representations about the suitability of this software for any purpose. It is provided "AS-IS" without warranty of any kind, either express or implied. 
