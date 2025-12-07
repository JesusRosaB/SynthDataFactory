import json
import csv
import os
import requests
from abc import ABC, abstractmethod

# Librerías opcionales (para que no falle si falta alguna al arrancar)
try:
    import paho.mqtt.client as mqtt
except ImportError: mqtt = None
try:
    from kafka import KafkaProducer
except ImportError: KafkaProducer = None
try:
    import pika
except ImportError: pika = None
try:
    import toml
except ImportError: toml = None
try:
    from dict2xml import dict2xml
except ImportError: dict2xml = None

class DataSink(ABC):
    @abstractmethod
    def send(self, data: dict): pass
    @abstractmethod
    def close(self): pass

class FileSink(DataSink):
    def __init__(self, filename, fmt='json'):
        self.filepath = filename
        self.fmt = fmt
        self.first_row = True
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        
        # Modo Append para ficheros grandes
        mode = 'w' 
        self.file = open(self.filepath, mode, encoding='utf-8')
        
        if self.fmt == 'json':
            self.file.write('[')
        elif self.fmt == 'xml':
            self.file.write('<root>\n')

    def send(self, data: dict):
        if self.fmt == 'json':
            if not self.first_row: self.file.write(',\n')
            self.file.write(json.dumps(data, ensure_ascii=False))
        elif self.fmt == 'csv':
            writer = csv.DictWriter(self.file, fieldnames=data.keys())
            if self.first_row: writer.writeheader()
            writer.writerow(data)
        elif self.fmt == 'toml' and toml:
            # TOML no soporta listas de objetos nativamente bien en stream,
            # así que lo guardamos como bloques separados por saltos
            self.file.write(toml.dumps(data) + "\n#---\n")
        elif self.fmt == 'xml' and dict2xml:
            self.file.write(dict2xml(data, wrap="record", indent="  ") + "\n")

        self.first_row = False

    def close(self):
        if self.fmt == 'json': self.file.write(']')
        elif self.fmt == 'xml': self.file.write('</root>')
        self.file.close()

class HttpSink(DataSink):
    def __init__(self, url):
        self.url = url
    def send(self, data: dict):
        try:
            requests.post(self.url, json=data, timeout=2)
        except Exception as e:
            print(f"Error HTTP: {e}")
    def close(self): pass

class KafkaSink(DataSink):
    def __init__(self, bootstrap_servers, topic):
        if not KafkaProducer: raise Exception("kafka-python no instalado")
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = topic
    def send(self, data: dict):
        self.producer.send(self.topic, data)
    def close(self):
        self.producer.flush()
        self.producer.close()

class RabbitMQSink(DataSink):
    def __init__(self, host, queue_name):
        if not pika: raise Exception("pika no instalado")
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=host))
        self.channel = self.connection.channel()
        self.queue = queue_name
        self.channel.queue_declare(queue=self.queue)
    def send(self, data: dict):
        self.channel.basic_publish(exchange='', routing_key=self.queue, body=json.dumps(data))
    def close(self):
        self.connection.close()

class MqttSink(DataSink):
    def __init__(self, host, port, topic):
        if not mqtt: raise Exception("paho-mqtt no instalado")
        self.client = mqtt.Client()
        self.topic = topic
        self.client.connect(host, int(port), 60)
        self.client.loop_start()
    def send(self, data: dict):
        self.client.publish(self.topic, json.dumps(data))
    def close(self):
        self.client.loop_stop()
        self.client.disconnect()

class ConsoleSink(DataSink):
    def send(self, data: dict): print(f"[LOG] {data}")
    def close(self): pass

# Factory
def get_sink(config: dict, sim_id: str, data_dir: str):
    t = config.get('target_type')
    
    if t == 'file':
        fmt = config.get('file_format', 'json')
        # Asumo que TOON es TOML o un typo, añado TOML y XML
        fname = os.path.join(data_dir, f"{config['simulation_name']}_{sim_id}.{fmt}")
        return FileSink(fname, fmt)
    elif t == 'http':
        return HttpSink(config['http_url'])
    elif t == 'kafka':
        return KafkaSink(config['kafka_bootstrap'], config['kafka_topic'])
    elif t == 'rabbitmq':
        return RabbitMQSink(config['rabbitmq_host'], config['rabbitmq_queue'])
    elif t == 'mqtt':
        return MqttSink(config['mqtt_host'], config['mqtt_port'], config['mqtt_topic'])
    elif t == 'console':
        return ConsoleSink()
    else:
        raise ValueError(f"Sink desconocido: {t}")