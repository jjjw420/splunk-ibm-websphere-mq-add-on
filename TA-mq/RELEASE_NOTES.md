# Version 1.5

Fix Python2 to Python3 conversion bugs.  Now been tested running bith Python 2 and Python 3.
Add time and source fields improvements.  Improved the `log_payload_as_event` option of the DefaultQueueResponseHandler to allow for the whole payload to used as the event.
Remove broken JSONhandler and tiggering code.

# Version 1.4

Python2 to Python3 conversion. 
Add `log_payload_as_event` option to the DefaultQueueResponseHandler to not log the message payload as a key value pair.
Add `payload_quote_char` option to the DefaultQueueResponseHandler to allow the quoting character for the "payload" key-value pair to be set.

# Version 1.3

Add support for MQ authentication.

# Version 1.2

Change to support PyMQI 1.5+

# Version 1.1

Add support for Channel Status messages.
Fix bug when building the MQMD in the DefaultQueueResponseHandler.
Fix default options for DefaultQueueResponseHandler.
Improve Documentation.

# Version 1.0

First Release.



