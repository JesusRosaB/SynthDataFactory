import time
import redis
import json
from datetime import datetime
from rq import Worker, Queue
from config import Config
from core.generator import generate_row
from core.sinks import get_sink

# Conexión a Redis
redis_conn = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)

def smart_sleep(seconds, status_key):
    """
    Duerme 'seconds' tiempo, pero despierta cada 0.1s para chequear
    si el usuario ha pulsado STOP o PAUSE. Devuelve True si debe parar.
    """
    waited = 0
    step = 0.1
    while waited < seconds:
        # Chequeo rápido a Redis
        try:
            current_status = redis_conn.hget(status_key, "status")
            if current_status:
                status = current_status.decode('utf-8')
                if status == "stopped":
                    return True  # Orden de parada recibida
                elif status == "paused":
                    # Esperar hasta que se reanude o se detenga
                    while True:
                        time.sleep(0.5)
                        current_status = redis_conn.hget(status_key, "status")
                        if current_status:
                            new_status = current_status.decode('utf-8')
                            if new_status == "running":
                                break  # Reanudar
                            elif new_status == "stopped":
                                return True  # Parar definitivamente
        except:
            pass  # Si falla redis momentaneamente, seguimos durmiendo

        time.sleep(step)
        waited += step
    return False

def simulation_task(sim_id, config):
    print(f"Worker: Iniciando simulación {sim_id}...")
    start_time = datetime.utcnow()

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
        # A) Chequeo de Parada/Pausa antes de generar
        current_status = redis_conn.hget(status_key, "status").decode('utf-8')
        if current_status == "stopped":
            print(f"Worker: Parada detectada en registro {i}")
            break
        elif current_status == "paused":
            print(f"Worker: Pausa detectada en registro {i}, esperando...")
            # Esperar hasta que se reanude o se detenga
            while True:
                time.sleep(0.5)
                current_status = redis_conn.hget(status_key, "status").decode('utf-8')
                if current_status == "running":
                    print(f"Worker: Simulación reanudada en registro {i}")
                    break
                elif current_status == "stopped":
                    print(f"Worker: Parada detectada durante pausa en registro {i}")
                    break
            if current_status == "stopped":
                break

        # B) Generar y Enviar
        try:
            row = generate_row(schema, sensor_pool=sensor_pool, step=i)
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
    final_current = int(redis_conn.hget(status_key, "current").decode('utf-8'))
    if final_status != "stopped" and final_status != "error":
        redis_conn.hset(status_key, mapping={"status": "completed", "current": total})

    # 6. Guardar en histórico
    end_time = datetime.utcnow()
    duration_seconds = (end_time - start_time).total_seconds()

    history_entry = {
        "sim_id": sim_id,
        "owner_user": config.get('owner_user', ''),
        "name": config.get('simulation_name', 'Unknown'),
        "status": final_status,
        "total_records": total,
        "completed_records": final_current if final_status == "stopped" else total,
        "target_type": config.get('target_type', 'file'),
        "file_format": config.get('file_format', 'json') if config.get('target_type') == 'file' else config.get('target_type', 'unknown'),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": round(duration_seconds, 2),
        "schema_field_count": len(schema)
    }

    # Guardar en Redis como lista ordenada (últimas 100 simulaciones)
    redis_conn.lpush("sim_history", json.dumps(history_entry))
    redis_conn.ltrim("sim_history", 0, 99)  # Mantener solo las últimas 100

    # También guardar con TTL de 7 días
    redis_conn.setex(f"sim_history:{sim_id}", 604800, json.dumps(history_entry))  # 7 días

    print(f"Worker: Simulación {sim_id} liberada.")

if __name__ == '__main__':
    print("Iniciando Worker de Mega Simulator...")
    worker = Worker(['default'], connection=redis_conn)
    worker.work()
