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

*The user name
mq_user_name= <value>

*The password
mq_password= <value>

*1 or more queue Names , comma delimited
queue_names= <value>

*How often to run the MQ input script
mqinput_interval= <value>

*Keep the MQ connection open
persistent_connection= <value>

*Whether to start a process dedicated per queue or whether to start a process that will service all queues sequentialy.
start_process_per_queue= <value>

*Start Multiple processes.
start_multiple_processes= <value>

*Number of processes to start.  Default 1.  
start_number_of_processes= <value>

*Python classname of custom response handler
response_handler= <value>

*Response Handler arguments string,  key=value,key2=value2
response_handler_args= <value>


[mqchs://<name>]

*Queue Manager name
queue_manager_name= <value>

queue_manager_name= <value> 
*IP or hostname of the remote queue manager
queue_manager_host= <value>

*The remote queue manager listener port(defaults to 1414)
port= <value>

*The server connection channel
server_connection_channel= <value>

*The user name
mq_user_name= <value>

*The password
mq_password= <value>

*One or more sender Channel Names, comma delimited, wild-cards allowed.
channel_names= <value>

*How often to run the MQ input script
mqchs_interval= <value>

*Keep the MQ connection open
persistent_connection= <value>

*Python classname of custom response handler
response_handler= <value>

*Response Handler arguments string ,  key=value,key2=value2
response_handler_args= <value>
