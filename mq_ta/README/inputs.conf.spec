[mqinput://<name>]

*Queue Manager name
queue_manager_name= <value>

queue_manager_name= <value> 
*IP or hostname of the remote queue manager
queue_manager_host= <value>

*The remote queue manager listener port(defaults to 1414)
port= <value>

*The server connection channel
server_connection_channel= <value>

*1 or more queue Names , comma delimited
queue_names= <value>

*How often to run the MQ input script
mqinput_interval= <value>

*Keep the MQ connection open
persistent_connection= <value>


*Whether or not to be trigger by websphere mq
use_mq_triggering= <value>


start_process_per_queue= <value>


*Python classname of custom response handler
response_handler= <value>

*Response Handler arguments string ,  key=value,key2=value2
response_handler_args= <value>
