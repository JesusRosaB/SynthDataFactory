import random
import uuid
import math
from faker import Faker
from datetime import datetime

fake = Faker('es_ES')

def generate_row(schema: list, sensor_pool: list = None, step: int = 0):
    row = {}
    
    # Lógica Mult-Sensor: Si hay un pool, elegimos uno al azar
    if sensor_pool:
        row['sensor_id'] = random.choice(sensor_pool)
        row['firmware_ver'] = "v1.4.2" # Dato extra de relleno para realismo

    for field in schema:
        # 1. Gestión de Nulos
        if random.randint(0, 100) < (field.get('null_percentage', 0)):
            row[field['name']] = None
            continue

        ftype = field['type']

        # --- TIPOS DE DATOS ---
        if ftype == 'uuid': val = str(uuid.uuid4())
        elif ftype == 'name': val = fake.name()
        elif ftype == 'email': val = fake.email()
        elif ftype == 'city': val = fake.city()
        elif ftype == 'country': val = fake.country()
        elif ftype == 'phone': val = fake.phone_number()
        elif ftype == 'address': val = fake.address().replace('\n', ', ')
        elif ftype == 'ip_address': val = fake.ipv4()
        elif ftype == 'latitude': val = round(float(fake.latitude()), 6)
        elif ftype == 'longitude': val = round(float(fake.longitude()), 6)
        elif ftype == 'credit_card': val = fake.credit_card_number()
        elif ftype == 'iban': val = fake.iban()
        elif ftype == 'company': val = fake.company()
        elif ftype == 'job': val = fake.job()
        elif ftype == 'url': val = fake.url()
        elif ftype == 'int':
            val = random.randint(int(field.get('min', 0)), int(field.get('max', 100)))
        elif ftype == 'float':
            val = round(random.uniform(float(field.get('min', 0)), float(field.get('max', 100))), 2)
        elif ftype == 'choice':
            options = field.get('options', [])
            weights = field.get('weights', None)
            if options:
                if weights and len(weights) == len(options):
                    val = random.choices(options, weights=weights, k=1)[0]
                else:
                    val = random.choice(options)
            else:
                val = None
        elif ftype == 'datetime': val = datetime.now().isoformat()
        elif ftype == 'timeseries':
            # Parámetros de configuración para series temporales
            base_value = float(field.get('base_value', 50.0))
            trend_slope = float(field.get('trend_slope', 0.0))  # pendiente de tendencia
            seasonal_amplitude = float(field.get('seasonal_amplitude', 0.0))  # amplitud estacional
            seasonal_period = float(field.get('seasonal_period', 10))  # período estacional
            noise_level = float(field.get('noise_level', 0.0))  # nivel de ruido

            # Calcular componentes
            trend_component = trend_slope * step
            seasonal_component = seasonal_amplitude * math.sin(2 * math.pi * step / seasonal_period) if seasonal_period > 0 else 0
            noise_component = random.uniform(-noise_level, noise_level) if noise_level > 0 else 0

            val = base_value + trend_component + seasonal_component + noise_component
            val = round(val, 2)
        else: val = "N/A"
        
        row[field['name']] = val
    
    # Metadata automática
    if '_timestamp' not in row:
        row['_timestamp'] = datetime.utcnow().isoformat()
        
    return row