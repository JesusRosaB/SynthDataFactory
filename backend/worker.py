import time
import redis
from rq import Worker, Queue
from config import Config
from core.generator import generate_row
from core.sinks import get_sink

# Conexión a Redis
redis_conn = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)

def smart_sleep(seconds, status_key):
    """
    Duerme 'seconds' tiempo, pero despierta cada 0.1s para chequear 
    si el usuario ha pulsado STOP. Devuelve True si debe parar.
    """
    waited = 0
    step = 0.1
    while waited < seconds:
        # Chequeo rápido a Redis
        try:
            current_status = redis_conn.hget(status_key, "status")
            if current_status and current_status.decode('utf-8') == "stopped":
                return True # Orden de parada recibida
        except:
            pass # Si falla redis momentaneamente, seguimos durmiendo
            
        time.sleep(step)
        waited += step
    return False

def simulation_task(sim_id, config):
    print(f"Worker: Iniciando simulación {sim_id}...")
    
    # 1. Configurar Sink (Salida)
    sink = None
    try:
        sink = get_sink(config, sim_id, Config.DATA_DIR)
    except Exception as e:
        print(f"Error fatal configurando Sink: {e}")
        # Marcar como error en Redis para que la UI se entere
        redis_conn.hset(f"sim_status:{sim_id}", "status", "error")
        return

    # 2. Leer configuración
    total = config.get('total_records', 100)
    delay = config.get('delay_seconds', 0)
    schema = config.get('schema_fields', [])
    
    # Lógica Multi-Sensor
    device_count = config.get('device_count', 1)
    sensor_pool = []
    if device_count > 1:
        import uuid
        sensor_pool = [f"SENSOR_{str(i+1).zfill(3)}_{str(uuid.uuid4())[:4]}" for i in range(device_count)]

    # 3. Inicializar estado
    status_key = f"sim_status:{sim_id}"
    redis_conn.hset(status_key, mapping={"status": "running", "total": total, "current": 0})

    # 4. BUCLE PRINCIPAL
    for i in range(total):
        # A) Chequeo de Parada antes de generar
        current_status = redis_conn.hget(status_key, "status").decode('utf-8')
        if current_status == "stopped":
            print(f"Worker: Parada detectada en registro {i}")
            break

        # B) Generar y Enviar
        try:
            row = generate_row(schema, sensor_pool=sensor_pool)
            sink.send(row)
        except Exception as e:
            print(f"Error generando/enviando fila: {e}")
            # Si falla el envío, no paramos todo, pero lo logueamos
            continue
        
        # C) Actualizar progreso (cada 10 o al final)
        if i % 10 == 0 or i == total - 1:
            redis_conn.hset(status_key, "current", i + 1)
        
        # D) SMART SLEEP (La magia para que pare rápido)
        if delay > 0:
            should_stop = smart_sleep(delay, status_key)
            if should_stop:
                print(f"Worker: Parada detectada durante el delay en registro {i}")
                break

    # 5. Limpieza Final
    print("Worker: Cerrando conexiones...")
    try:
        sink.close()
    except Exception as e:
        print(f"Error cerrando sink: {e}")
    
    # Solo marcamos como completado si no fue parado manualmente
    final_status = redis_conn.hget(status_key, "status").decode('utf-8')
    if final_status != "stopped" and final_status != "error":
        redis_conn.hset(status_key, mapping={"status": "completed", "current": total})
    
    print(f"Worker: Simulación {sim_id} liberada.")

if __name__ == '__main__':
    print("Iniciando Worker de Mega Simulator...")
    worker = Worker(['default'], connection=redis_conn)
    worker.work()