# Log Aggregator
## Use
This script has a GELF in- and output to aggregate messages based on keys and values to aggregate.  
It is intended as a Graylog version independent successor to the [Context Collector](https://github.com/NetUSE-AG/graylog-plugin-context-collector)

## Usage 
### Install 
~~~
python3 -m venv venv
venv/bin/pip3 install -r requirements.txt
~~~
Change paths in log\_aggregator.service  
Change ip/ports for I/O GELF in config.yaml
~~~
mv log_aggregator.service /etc/systemd/system/log_aggregator.service
systemctl daemon-reload
systemctl enable log_aggregator.service
systemctl start log_aggregator.service
~~~
In Graylog add a GELF/TCP Output to the socket the script opened  
In Graylog add a GELF/TCP Input on the port defined in config.yaml  
Restart Service after config changes

### Routing
In Graylog route all Logs you need for aggregations in one Stream, which the Output runs on.  
Make new routing-pipeline rules for the aggregated logs if the routing rule for the logs to aggregate is based on input ids. The Logs contain the same fields so the normal routing pipeline-rules will route them correctly otherwise.  

Example Routing Rule: 
~~~
rule "route_to_log_aggregator"
when
    (
        false || // condition for first aggregations logs
        false    // condition for second aggregations logs
    ) and 
    not has_field("aggregation_name")
then
    route_to_stream(id:"6a314ac95da0315da0e3def5"); //Log Aggregator Stream/Output
end
~~~

## Config
~~~
listen:
  host: 0.0.0.0 # interface to listen on. 0.0.0.0 for all interfaces 
  port: 10000 # port to listen on. TCP GELF

output:
  host: 127.0.0.1 # ip of upstream server(Graylog or Load-Balancer)
  port: 10001 # port of the upstream server
  protocol: tcp # upstream protocol. "tcp" or "udp" 

aggregations:
  - name: aggregation1 # name of the aggregation. visible in the aggregated logs as "aggregation_name"
    flush_after: 10 # time to wait in seconds until aggregations are flushed.
    drop_incomplete: False # True: aggregation will be dropped when not all fields are collected.  False: aggregation will be send partially when "flush_after" ttl is reached. The state of the aggregation will be reported in field "aggregation_complete"
    all_fields: True # True: aggregates all fields in the Logs False: aggregates only fields in "group_by" and "fields"
    group_by: # fields used as aggregation keys 
      - key1
      - key2
    fields: # fields to aggregate 
      - field1
      - field2
      - field3

  - name: aggregation2
    flush_after: 10 
    drop_incomplete: True
    all_fields: True
    group_by:
      - key3
      - key4
    fields:
      - field1
      - field2 
~~~
