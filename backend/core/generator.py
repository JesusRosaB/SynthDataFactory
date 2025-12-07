import random
import uuid
from faker import Faker
from datetime import datetime

fake = Faker('es_ES')

def generate_row(schema: list, sensor_pool: list = None):
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
        else: val = "N/A"
        
        row[field['name']] = val
    
    # Metadata automática
    if '_timestamp' not in row:
        row['_timestamp'] = datetime.utcnow().isoformat()
        
    return row