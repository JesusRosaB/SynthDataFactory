import uuid
import redis
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from rq import Queue
from config import Config
from worker import simulation_task
from i18n import TEXTS

redis_conn = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT)
q = Queue(connection=redis_conn)

class FieldSchema(BaseModel):
    name: str = Field(..., description="Nombre del campo / Field Name", example="temperature")
    type: str = Field(..., description="Tipo de dato / Data Type (integer, float, categorical, city...)", example="float")
    options: Optional[List[str]] = Field(None, description="Opciones para 'categorical' / Options for 'categorical'")
    weights: Optional[List[float]] = Field(None, description="Pesos probabilísticos / Probabilistic weights")
    min: Optional[float] = Field(None, description="Valor mínimo / Min value")
    max: Optional[float] = Field(None, description="Valor máximo / Max value")
    null_percentage: int = Field(0, description="% Nulos / % Nulls", ge=0, le=100)

class SimConfig(BaseModel):
    simulation_name: str = Field(..., description="Nombre de simulación / Simulation Name")
    total_records: int = Field(..., description="Total registros / Total records", gt=0)
    delay_seconds: float = Field(0, description="Retraso (segundos) / Delay (seconds)", ge=0)
    device_count: int = Field(1, description="Cantidad dispositivos / Device count", gt=0)
    
    target_type: str = Field(..., description="Destino (file, mqtt, kafka...) / Target type")
    file_format: Optional[str] = Field('json', description="Formato de archivo / File format")
    
    mqtt_host: Optional[str] = Field(None, description="MQTT Host")
    mqtt_port: Optional[int] = Field(1883, description="MQTT Port")
    mqtt_topic: Optional[str] = Field(None, description="MQTT Topic")
    kafka_bootstrap: Optional[str] = Field(None, description="Kafka Bootstrap Servers")
    kafka_topic: Optional[str] = Field(None, description="Kafka Topic")
    http_url: Optional[str] = Field(None, description="HTTP Webhook URL")
    rabbitmq_host: Optional[str] = Field(None, description="RabbitMQ Host")
    rabbitmq_queue: Optional[str] = Field(None, description="RabbitMQ Queue")

    schema_fields: List[FieldSchema] = Field(..., description="Esquema de campos / Field Schema")

class SimulationResponse(BaseModel):
    message: str
    sim_id: str

class StopResponse(BaseModel):
    message: str

class FileListResponse(BaseModel):
    files: List[str]

def create_app(lang: str = "es") -> FastAPI:
    """
    Crea una instancia de FastAPI configurada con el idioma especificado.
    """
    t = TEXTS.get(lang, TEXTS["es"])
    meta = t["meta"]
    endpoints = t["endpoints"]
    
    tags_metadata = meta["tags"]
    
    tag_sim = tags_metadata[0]["name"]
    tag_files = tags_metadata[1]["name"]

    app = FastAPI(
        title=meta["title"],
        description=meta["description"],
        version="1.0.0",
        contact={"name": meta["contact_name"], "url": "https://github.com/JesusRosaB/SynthDataFactory"},
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        openapi_tags=tags_metadata,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    @app.post("/api/simulation/start", response_model=SimulationResponse, tags=[tag_sim],
              summary=endpoints["start"]["summary"], description=endpoints["start"]["desc"])
    def start_simulation(config: SimConfig):
        sim_id = str(uuid.uuid4())[:8]
        
        redis_conn.hset(f"sim_status:{sim_id}", mapping={
            "name": config.simulation_name,
            "status": "queued",
            "total": config.total_records,
            "current": 0
        })
        
        q.enqueue(simulation_task, sim_id, config.dict())
        
        return {"message": endpoints["start"]["response"], "sim_id": sim_id}

    @app.post("/api/simulation/stop/{sim_id}", response_model=StopResponse, tags=[tag_sim],
              summary=endpoints["stop"]["summary"], description=endpoints["stop"]["desc"])
    def stop_simulation(sim_id: str):
        key = f"sim_status:{sim_id}"
        if redis_conn.exists(key):
            redis_conn.hset(key, "status", "stopped")
            return {"message": endpoints["stop"]["response"]}
        raise HTTPException(status_code=404, detail=endpoints["stop"]["error_404"])

    @app.get("/api/simulation/all", tags=[tag_sim],
             summary=endpoints["all"]["summary"], description=endpoints["all"]["desc"])
    def get_all_status():
        keys = redis_conn.keys("sim_status:*")
        results = {}
        for key in keys:
            k_str = key.decode('utf-8')
            sid = k_str.split(":")[1]
            data = redis_conn.hgetall(k_str)
            results[sid] = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items()}
        return results

    @app.get("/api/files", response_model=FileListResponse, tags=[tag_files],
             summary=endpoints["list_files"]["summary"], description=endpoints["list_files"]["desc"])
    def list_files():
        if not os.path.exists(Config.DATA_DIR):
            return {"files": []}
        all_files = os.listdir(Config.DATA_DIR)
        visible_files = [f for f in all_files if not f.startswith('.')]
        visible_files.sort(reverse=True)
        return {"files": visible_files}

    @app.get("/api/files/download/{filename}", tags=[tag_files],
             summary=endpoints["download"]["summary"], description=endpoints["download"]["desc"])
    def download_file(filename: str):
        path = os.path.join(Config.DATA_DIR, filename)
        if os.path.exists(path):
            return FileResponse(path, filename=filename)
        raise HTTPException(status_code=404, detail=endpoints["download"]["error_404"])

    return app

app = create_app(lang="es")
app_en = create_app(lang="en")
app.mount("/en", app_en)

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)