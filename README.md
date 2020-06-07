# splunk-ibm-websphere-mq-add-on - TA-mq

By Hannes Wagener - 2015 

## Overview

This is a Splunk modular input add-on for IBM Websphere MQ.
Currently two data inputs are supported.  One for creating events from messages on IBM Websphere queues and another for channel status statistics.

Created from the Splunk modular input examples.

## Features

* Simple UI based configuration via Splunk Manager
* Poll  IBM Websphere MQ queues at interval or can be triggered from the Websphere MQ trigger monitor(future feature).
* Poll IBM Websphere MQ Channel Status statistics.
* Uses regular splunk sourcetypes to process message ("Generic single line" or "syslog") 
* You can specify multiple queues or channels per data input.  You can specify whether to use a thread per data input or per queue/channel.
* Automatic thread management.  No need to restart splunk after changes are made to a data input.  This includes adding and removing queues.
* Includes default response handlers for queue input and channel status input.
* Includes a response handler for IBM Websphere Message Broker monitoring events.

## Dependencies

* Splunk 6.0+
* PyMQI 1.5+
* ctypes library for Python.  **NOTE: Splunk V8 has the ctypes libary installed by default for both Python2 and Python3.**  
* IBM Websphere MQ Client Libraries V7+
* Only currently supported on Linux (but Windows (and any other platform) should be possible if the platform versions of the PyMQI and ctypes libraries are installed) 

## Setup

* Install the IBM Websphere MQ client.  Ensure that the user that runs splunk has access to the MQ client libraries.  The easiest way to achieve this is to add the MQ client library locations (generaly /opt/mqm/lib) to the dynamic loader configuration (ld.so.conf). 
* Get and build the PyMQI library.  You can download from here: https://github.com/dsuch/pymqi 
* Untar the MQ modular input release to your $SPLUNK_HOME/etc/apps directory.
* Copy the built PyMQI library to the $SPLUNK_HOME/etc/apps/TA-mq/bin folder.
* Copy python c_types library directory to the $SPLUNK_HOME/etc/apps/TA-mq/bin directory.  Splunk's Python interpreter is built with UCS-2.  Make sure you use a compatible _ctypes.so library.  **NOTE:  This step is not required if running Splunk V8+as the ctypes library is included for both Python2 and Python3.**  
* Ensure that the pymqi and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Restart Splunk



## Response Handlers
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
   * `log_payload_as_event` - If false do not log the payload as a name/value pair.  Default: false
   * `payload_quote_char` - Use a specific character to quote the "payload" kv value. Default: " (double quote)

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
  * `write_events = true/false` - Write out the events to disk.  
  * `gzip_events = true/false` - Gzip the events written to disk.
  * `write_events_folder = "/opt/brokerevents"` - Directory to which events must be written.  


## Logging

Any modular input log errors will get written to $SPLUNK_HOME/var/log/splunk/splunkd.log.  Debug logging can be "enabled by changing the "ExecProcessor" property under "Server logging" to DEBUG.

## Troubleshooting

* You are using Splunk 6+
* Look for any errors in $SPLUNK_HOME/var/log/splunk/splunkd.log
* Enable debug logging by changing the "ExecProcessor" property under "Server logging" to DEBUG.  This will output some debug at various places in the code.  
Search for the following in Splunk: `index=_internal component=ExecProcessor TA-mq`
* Ensure that the PyMQI and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Ensure that the IBM Websphere MQ libraries are available to the user which runs Splunk. 


## DISCLAIMER
You are free to use this code in any way you like, subject to the Python & IBM disclaimers & copyrights. I make no representations about the suitability of this software for any purpose. It is provided "AS-IS" without warranty of any kind, either express or implied. 
