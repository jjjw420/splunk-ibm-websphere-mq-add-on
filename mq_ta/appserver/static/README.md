## IBM Websphere MQ Modular Input
# DISCLAIMER
# You are free to use this code in any way you like, subject to the
# Python & IBM disclaimers & copyrights. I make no representations
# about the suitability of this software for any purpose. It is
# provided "AS-IS" without warranty of any kind, either express or
# implied. 
##

By Hannes Wagener - 2014 (johannes.wagener420@gmail.com) 

## Overview

This is a Splunk modular input add-on for creating events from messages on IBM Websphere queues.

## Features

* Simple UI based configuration via Splunk Manager
* Poll queues at interval or can be triggered from the Websphere MQ trigger monitor.
* Uses regular splunk sourcetypes to process message ("Generic single line" or "syslog") 
* You can specify multiple queues per data input.  You can specify whether to use a thread per data input or per queue.
* Automatic thread management.  No need to restart splunk after changes are made to a data input.  This includes adding and removing queues.

## Dependencies

* Splunk 6.0+
* PyMQI 1.2+
* ctypes library for Python
* IBM Websphere MQ Client Libraries V7+
* Only currently supported on Linux (but Windows (and any other platform) should be possible if the platform versions of the PyMQI and ctypes libraries are installed) 


## Setup

* Install the IBM Websphere MQ client.  
* Get and build the PyMQI library.  You can download from here: https://github.com/dsuch/pymqi 
* Untar the MQ modular input release to your $SPLUNK_HOME/etc/apps directory.
* Copy the built PyMQI libraries to the $SPLUNK_HOME/etc/apps/mq_ta/bin folder (i.e. copy pymqi.py, pymqe.so, CMQC.py, CMQCFC.py, CMQXC.py, and CMQZC.py to the $SPLUNK_HOME/etc/apps/mq_ta/bin directory).  
* Copy python c_types library directory to the $SPLUNK_HOME/etc/apps/mq_ta/bin directory.  
* Ensure that the pymqi and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Restart Splunk


## Logging

Any modular input log errors will get written to $SPLUNK_HOME/var/log/splunk/splunkd.log.  Debug logging can be "enabled by changing the "ExecProcessor" property under "Server logging" to DEBUG.

## Troubleshooting

* You are using Splunk 6+
* Look for any errors in $SPLUNK_HOME/var/log/splunk/splunkd.log
* Enable debug logging by changing the "ExecProcessor" property under "Server logging" to DEBUG.
* Ensure that the PyMQI and ctypes libraries can be imported when using the Splunk Python interpreter. 
* Ensure that the IBM Websphere MQ libraries are available to the user which runs Splunk. 


