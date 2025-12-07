import uuid
import redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from rq import Queue
from config import Config
from worker import simulation_task
import os

app = FastAPI()

# Conexión Redis y Cola
redis_conn = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
q = Queue(connection=redis_conn)

# --- Modelos Pydantic ---
class FieldSchema(BaseModel):
    name: str
    type: str
    options: Optional[List[str]] = None
    weights: Optional[List[float]] = None # Probabilidades para options
    min: Optional[float] = None
    max: Optional[float] = None
    null_percentage: int = 0

class SimConfig(BaseModel):
    simulation_name: str
    total_records: int
    delay_seconds: float = 0
    device_count: int = 1  # NUEVO: Multi-sensor
    
    target_type: str 
    file_format: Optional[str] = 'json' 
    
    # Configs de Sinks
    mqtt_host: Optional[str] = None
    mqtt_port: Optional[int] = 1883
    mqtt_topic: Optional[str] = None
    
    kafka_bootstrap: Optional[str] = None # NUEVO
    kafka_topic: Optional[str] = None     # NUEVO
    
    http_url: Optional[str] = None        # NUEVO
    
    rabbitmq_host: Optional[str] = None   # NUEVO
    rabbitmq_queue: Optional[str] = None  # NUEVO

    schema_fields: List[FieldSchema]

@app.post("/api/simulation/start")
def start_simulation(config: SimConfig):
    sim_id = str(uuid.uuid4())[:8]
    
    # Inicializar estado en Redis
    redis_conn.hset(f"sim_status:{sim_id}", mapping={
        "name": config.simulation_name,
        "status": "queued",
        "total": config.total_records,
        "current": 0
    })
    
    # Encolar trabajo para el worker
    q.enqueue(simulation_task, sim_id, config.dict())
    
    return {"message": "Simulación encolada", "sim_id": sim_id}

@app.post("/api/simulation/stop/{sim_id}")
def stop_simulation(sim_id: str):
    key = f"sim_status:{sim_id}"
    if redis_conn.exists(key):
        redis_conn.hset(key, "status", "stopped")
        return {"message": "Señal de parada enviada"}
    raise HTTPException(status_code=404, detail="Simulación no encontrada")

@app.get("/api/simulation/all")
def get_all_status():
    """ Escanea Redis para buscar todas las simulaciones """
    keys = redis_conn.keys("sim_status:*")
    results = {}
    for key in keys:
        k_str = key.decode('utf-8')
        sid = k_str.split(":")[1]
        data = redis_conn.hgetall(k_str)
        results[sid] = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}
    return results

@app.get("/api/files")
def list_files():
    all_files = os.listdir(Config.DATA_DIR)
    visible_files = [f for f in all_files if not f.startswith('.')]
    visible_files.sort(reverse=True)
    return {"files": visible_files}

@app.get("/api/files/download/{filename}")
def download_file(filename: str):
    path = os.path.join(Config.DATA_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path, filename=filename)
    raise HTTPException(status_code=404, detail="Archivo no encontrado")