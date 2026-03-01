import json
import csv
import os
import requests
import re
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
try:
    import psycopg2
    from psycopg2 import sql as psycopg2_sql
except ImportError:
    psycopg2 = None
    psycopg2_sql = None
try:
    import pymongo
except ImportError:
    pymongo = None
try:
    import mysql.connector as mysql_connector
except ImportError:
    mysql_connector = None

class DataSink(ABC):
    @abstractmethod
    def send(self, data: dict): pass
    @abstractmethod
    def close(self): pass

def _validate_identifier(value: str, label: str) -> str:
    if not value or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        raise ValueError(f"{label} inválido: usa solo letras, números y guion bajo")
    return value

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
        elif self.fmt == 'toml':
            # TOML standard format - will write a single TOML document
            self.file.write('# TOML Document\n\n')

    def send(self, data: dict):
        if self.fmt == 'json':
            if not self.first_row: self.file.write(',\n')
            self.file.write(json.dumps(data, ensure_ascii=False))
        elif self.fmt == 'csv':
            writer = csv.DictWriter(self.file, fieldnames=data.keys())
            if self.first_row: writer.writeheader()
            writer.writerow(data)
        elif self.fmt == 'toml' and toml:
            # TOML standard: writes each record as a table entry
            record_name = f"record_{hash(frozenset(data.items())) % 10000}"
            self.file.write(f"[{record_name}]\n")
            self.file.write(toml.dumps(data) + "\n")
        elif self.fmt == 'toon' and toml:
            # TOON format: streaming blocks separated by delimiters
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

class PostgreSQLSink(DataSink):
    def __init__(self, host, port, database, user, password, table):
        if not psycopg2:
            raise Exception("psycopg2-binary no instalado")

        self.table = _validate_identifier(table, "Nombre de tabla PostgreSQL")
        self.conn = psycopg2.connect(
            host=host,
            port=int(port),
            dbname=database,
            user=user,
            password=password
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()

        create_stmt = psycopg2_sql.SQL(
            """
            CREATE TABLE IF NOT EXISTS {} (
                id BIGSERIAL PRIMARY KEY,
                payload JSONB NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
            )
            """
        ).format(psycopg2_sql.Identifier(self.table))
        self.cur.execute(create_stmt)

    def send(self, data: dict):
        insert_stmt = psycopg2_sql.SQL("INSERT INTO {} (payload) VALUES (%s)").format(
            psycopg2_sql.Identifier(self.table)
        )
        self.cur.execute(insert_stmt, [json.dumps(data, ensure_ascii=False)])

    def close(self):
        try:
            self.cur.close()
        finally:
            self.conn.close()

class MongoDBSink(DataSink):
    def __init__(self, uri, database, collection):
        if not pymongo:
            raise Exception("pymongo no instalado")

        if not database:
            raise ValueError("Nombre de base de datos MongoDB requerido")
        if not collection:
            raise ValueError("Nombre de colección MongoDB requerido")
        self.client = pymongo.MongoClient(uri)
        self.collection = self.client[database][collection]

    def send(self, data: dict):
        self.collection.insert_one(data)

    def close(self):
        self.client.close()

class MySQLSink(DataSink):
    def __init__(self, host, port, database, user, password, table):
        if not mysql_connector:
            raise Exception("mysql-connector-python no instalado")

        self.table = _validate_identifier(table, "Nombre de tabla MySQL")
        self.conn = mysql_connector.connect(
            host=host,
            port=int(port),
            database=database,
            user=user,
            password=password,
            autocommit=True
        )
        self.cur = self.conn.cursor()
        self.cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{self.table}` (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                payload JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def send(self, data: dict):
        self.cur.execute(
            f"INSERT INTO `{self.table}` (payload) VALUES (%s)",
            [json.dumps(data, ensure_ascii=False)]
        )

    def close(self):
        try:
            self.cur.close()
        finally:
            self.conn.close()

# Factory
def get_sink(config: dict, sim_id: str, data_dir: str):
    t = config.get('target_type')
    
    if t == 'file':
        fmt = config.get('file_format', 'json')
        owner_user = config.get("owner_user", "anon")
        fname = os.path.join(data_dir, f"{owner_user}__{config['simulation_name']}_{sim_id}.{fmt}")
        return FileSink(fname, fmt)
    elif t == 'http':
        return HttpSink(config['http_url'])
    elif t == 'kafka':
        return KafkaSink(config['kafka_bootstrap'], config['kafka_topic'])
    elif t == 'rabbitmq':
        return RabbitMQSink(config['rabbitmq_host'], config['rabbitmq_queue'])
    elif t == 'mqtt':
        return MqttSink(config['mqtt_host'], config['mqtt_port'], config['mqtt_topic'])
    elif t == 'postgres':
        return PostgreSQLSink(
            config['postgres_host'],
            config.get('postgres_port', 5432),
            config['postgres_db'],
            config['postgres_user'],
            config['postgres_password'],
            config.get('postgres_table', 'synthetic_data')
        )
    elif t == 'mongodb':
        return MongoDBSink(
            config.get('mongodb_uri', 'mongodb://localhost:27017'),
            config['mongodb_db'],
            config.get('mongodb_collection', 'synthetic_data')
        )
    elif t == 'mysql':
        return MySQLSink(
            config['mysql_host'],
            config.get('mysql_port', 3306),
            config['mysql_db'],
            config['mysql_user'],
            config['mysql_password'],
            config.get('mysql_table', 'synthetic_data')
        )
    elif t == 'console':
        return ConsoleSink()
    else:
        raise ValueError(f"Sink desconocido: {t}")
