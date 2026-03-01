import uuid
import redis
import os
import json
import hashlib
import secrets
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from rq import Queue
from config import Config
from worker import simulation_task
from i18n import TEXTS

# Import GROQ (optional)
try:
    from groq import Groq
except ImportError:
    Groq = None

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
    
    target_type: str = Field(..., description="Destino (file, mqtt, kafka, http, rabbitmq, postgres, mongodb, mysql) / Target type")
    file_format: Optional[str] = Field('json', description="Formato de archivo / File format")
    
    mqtt_host: Optional[str] = Field(None, description="MQTT Host")
    mqtt_port: Optional[int] = Field(1883, description="MQTT Port")
    mqtt_topic: Optional[str] = Field(None, description="MQTT Topic")
    kafka_bootstrap: Optional[str] = Field(None, description="Kafka Bootstrap Servers")
    kafka_topic: Optional[str] = Field(None, description="Kafka Topic")
    http_url: Optional[str] = Field(None, description="HTTP Webhook URL")
    rabbitmq_host: Optional[str] = Field(None, description="RabbitMQ Host")
    rabbitmq_queue: Optional[str] = Field(None, description="RabbitMQ Queue")
    postgres_host: Optional[str] = Field(None, description="PostgreSQL Host")
    postgres_port: Optional[int] = Field(5432, description="PostgreSQL Port")
    postgres_db: Optional[str] = Field(None, description="PostgreSQL Database")
    postgres_user: Optional[str] = Field(None, description="PostgreSQL User")
    postgres_password: Optional[str] = Field(None, description="PostgreSQL Password")
    postgres_table: Optional[str] = Field("synthetic_data", description="PostgreSQL Table")
    mongodb_uri: Optional[str] = Field("mongodb://localhost:27017", description="MongoDB URI")
    mongodb_db: Optional[str] = Field(None, description="MongoDB Database")
    mongodb_collection: Optional[str] = Field("synthetic_data", description="MongoDB Collection")
    mysql_host: Optional[str] = Field(None, description="MySQL Host")
    mysql_port: Optional[int] = Field(3306, description="MySQL Port")
    mysql_db: Optional[str] = Field(None, description="MySQL Database")
    mysql_user: Optional[str] = Field(None, description="MySQL User")
    mysql_password: Optional[str] = Field(None, description="MySQL Password")
    mysql_table: Optional[str] = Field("synthetic_data", description="MySQL Table")

    schema_fields: List[FieldSchema] = Field(..., description="Esquema de campos / Field Schema")

class SimulationResponse(BaseModel):
    message: str
    sim_id: str

class StopResponse(BaseModel):
    message: str

class FileListResponse(BaseModel):
    files: List[str]

class AISchemaRequest(BaseModel):
    description: str = Field(..., description="Descripción de los datos a simular / Description of data to simulate", example="Sensores IoT de temperatura y humedad")

class AISchemaResponse(BaseModel):
    schema_fields: List[FieldSchema]
    simulation_name: str
    suggested_records: int
    suggested_target_type: Optional[str] = None
    suggested_sink_config: Optional[Dict[str, Any]] = None

class AuthRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)

class AuthResponse(BaseModel):
    message: str
    token: str
    username: str

class AuthMeResponse(BaseModel):
    username: str

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def _sanitize_username(username: str) -> str:
    normalized = "".join(ch for ch in username.strip().lower() if ch.isalnum() or ch in ("_", "-"))
    return normalized

def _extract_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.strip().split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None

def _resolve_user_from_token(token: Optional[str]) -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    username_raw = redis_conn.get(f"auth_token:{token}")
    if not username_raw:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username_raw.decode("utf-8")

def get_current_user(authorization: Optional[str] = Header(None, alias="Authorization")) -> str:
    token = _extract_token(authorization)
    return _resolve_user_from_token(token)

def get_current_user_for_download(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    bearer_token = _extract_token(authorization)
    resolved_token = bearer_token or token
    return _resolve_user_from_token(resolved_token)

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
        version="2.2.0",
        contact={"name": meta["contact_name"], "url": "https://github.com/JesusRosaB/SynthDataFactory"},
        license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
        openapi_tags=tags_metadata,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    @app.post("/api/auth/register", response_model=AuthResponse, tags=["Authentication"],
              summary="Registrar usuario / Register user")
    def register_user(payload: AuthRegisterRequest):
        username = _sanitize_username(payload.username)
        if len(username) < 3:
            raise HTTPException(status_code=400, detail="Invalid username")

        user_key = f"user:{username}"
        if redis_conn.exists(user_key):
            raise HTTPException(status_code=409, detail="User already exists")

        salt = secrets.token_hex(16)
        pwd_hash = _hash_password(payload.password, salt)
        redis_conn.hset(user_key, mapping={
            "username": username,
            "salt": salt,
            "password_hash": pwd_hash,
            "created_at": datetime.utcnow().isoformat()
        })

        token = secrets.token_urlsafe(32)
        redis_conn.setex(f"auth_token:{token}", Config.AUTH_TOKEN_TTL_SECONDS, username)
        return {"message": "User registered", "token": token, "username": username}

    @app.post("/api/auth/login", response_model=AuthResponse, tags=["Authentication"],
              summary="Iniciar sesión / Login")
    def login_user(payload: AuthLoginRequest):
        username = _sanitize_username(payload.username)
        user_key = f"user:{username}"
        if not redis_conn.exists(user_key):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_data = redis_conn.hgetall(user_key)
        salt = user_data.get(b"salt", b"").decode("utf-8")
        stored_hash = user_data.get(b"password_hash", b"").decode("utf-8")
        if _hash_password(payload.password, salt) != stored_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = secrets.token_urlsafe(32)
        redis_conn.setex(f"auth_token:{token}", Config.AUTH_TOKEN_TTL_SECONDS, username)
        return {"message": "Login successful", "token": token, "username": username}

    @app.post("/api/auth/logout", tags=["Authentication"],
              summary="Cerrar sesión / Logout")
    def logout_user(authorization: Optional[str] = Header(None, alias="Authorization")):
        token = _extract_token(authorization)
        if token:
            redis_conn.delete(f"auth_token:{token}")
        return {"message": "Logged out"}

    @app.get("/api/auth/me", response_model=AuthMeResponse, tags=["Authentication"],
             summary="Usuario actual / Current user")
    def auth_me(current_user: str = Depends(get_current_user)):
        return {"username": current_user}

    @app.post("/api/simulation/start", response_model=SimulationResponse, tags=[tag_sim],
              summary=endpoints["start"]["summary"], description=endpoints["start"]["desc"])
    def start_simulation(config: SimConfig, current_user: str = Depends(get_current_user)):
        sim_id = str(uuid.uuid4())[:8]
        
        redis_conn.hset(f"sim_status:{sim_id}", mapping={
            "owner": current_user,
            "name": config.simulation_name,
            "status": "queued",
            "total": config.total_records,
            "current": 0
        })

        config_payload = config.dict()
        config_payload["owner_user"] = current_user
        q.enqueue(simulation_task, sim_id, config_payload)
        
        return {"message": endpoints["start"]["response"], "sim_id": sim_id}

    @app.post("/api/simulation/stop/{sim_id}", response_model=StopResponse, tags=[tag_sim],
              summary=endpoints["stop"]["summary"], description=endpoints["stop"]["desc"])
    def stop_simulation(sim_id: str, current_user: str = Depends(get_current_user)):
        key = f"sim_status:{sim_id}"
        if redis_conn.exists(key):
            owner_raw = redis_conn.hget(key, "owner")
            owner = owner_raw.decode("utf-8") if owner_raw else ""
            if owner != current_user:
                raise HTTPException(status_code=403, detail="Forbidden")
            redis_conn.hset(key, "status", "stopped")
            return {"message": endpoints["stop"]["response"]}
        raise HTTPException(status_code=404, detail=endpoints["stop"]["error_404"])

    @app.post("/api/simulation/pause/{sim_id}", response_model=StopResponse, tags=[tag_sim],
              summary="Pausar simulación / Pause simulation",
              description="Pausa temporalmente una simulación en ejecución / Temporarily pauses a running simulation")
    def pause_simulation(sim_id: str, current_user: str = Depends(get_current_user)):
        key = f"sim_status:{sim_id}"
        if redis_conn.exists(key):
            owner_raw = redis_conn.hget(key, "owner")
            owner = owner_raw.decode("utf-8") if owner_raw else ""
            if owner != current_user:
                raise HTTPException(status_code=403, detail="Forbidden")
            current_status = redis_conn.hget(key, "status")
            if current_status and current_status.decode('utf-8') == "running":
                redis_conn.hset(key, "status", "paused")
                return {"message": "Simulation paused successfully"}
            else:
                raise HTTPException(status_code=400, detail="Simulation is not running")
        raise HTTPException(status_code=404, detail="Simulation not found")

    @app.post("/api/simulation/resume/{sim_id}", response_model=StopResponse, tags=[tag_sim],
              summary="Reanudar simulación / Resume simulation",
              description="Reanuda una simulación pausada / Resumes a paused simulation")
    def resume_simulation(sim_id: str, current_user: str = Depends(get_current_user)):
        key = f"sim_status:{sim_id}"
        if redis_conn.exists(key):
            owner_raw = redis_conn.hget(key, "owner")
            owner = owner_raw.decode("utf-8") if owner_raw else ""
            if owner != current_user:
                raise HTTPException(status_code=403, detail="Forbidden")
            current_status = redis_conn.hget(key, "status")
            if current_status and current_status.decode('utf-8') == "paused":
                redis_conn.hset(key, "status", "running")
                return {"message": "Simulation resumed successfully"}
            else:
                raise HTTPException(status_code=400, detail="Simulation is not paused")
        raise HTTPException(status_code=404, detail="Simulation not found")

    @app.get("/api/simulation/all", tags=[tag_sim],
             summary=endpoints["all"]["summary"], description=endpoints["all"]["desc"])
    def get_all_status(current_user: str = Depends(get_current_user)):
        keys = redis_conn.keys("sim_status:*")
        results = {}
        for key in keys:
            k_str = key.decode('utf-8')
            sid = k_str.split(":")[1]
            data = redis_conn.hgetall(k_str)
            owner = data.get(b"owner", b"").decode("utf-8")
            if owner != current_user:
                continue
            results[sid] = {k.decode('utf-8'): v.decode('utf-8') for k, v in data.items() if k.decode('utf-8') != "owner"}
        return results

    @app.get("/api/simulation/history", tags=[tag_sim],
             summary="Obtener histórico de simulaciones / Get simulation history",
             description="Retorna las últimas 100 simulaciones completadas / Returns last 100 completed simulations")
    def get_simulation_history(current_user: str = Depends(get_current_user)):
        history_items = redis_conn.lrange("sim_history", 0, 99)
        history = []
        for item in history_items:
            try:
                parsed = json.loads(item.decode('utf-8'))
                if parsed.get("owner_user") == current_user:
                    history.append(parsed)
            except:
                continue
        return {"history": history}

    @app.get("/api/simulation/stats", tags=[tag_sim],
             summary="Obtener estadísticas agregadas / Get aggregated statistics",
             description="Calcula métricas del histórico de simulaciones / Calculates metrics from simulation history")
    def get_simulation_stats(current_user: str = Depends(get_current_user)):
        history_items = redis_conn.lrange("sim_history", 0, 99)
        history = []
        for item in history_items:
            try:
                parsed = json.loads(item.decode('utf-8'))
                if parsed.get("owner_user") == current_user:
                    history.append(parsed)
            except:
                continue

        if not history:
            return {
                "total_simulations": 0,
                "total_records": 0,
                "avg_duration": 0,
                "by_status": {},
                "by_format": {},
                "recent_activity": []
            }

        # Calcular estadísticas
        total_simulations = len(history)
        total_records = sum(item.get('completed_records', 0) for item in history)
        total_duration = sum(item.get('duration_seconds', 0) for item in history)
        avg_duration = round(total_duration / total_simulations, 2) if total_simulations > 0 else 0

        # Distribución por estado
        by_status = {}
        for item in history:
            status = item.get('status', 'unknown')
            by_status[status] = by_status.get(status, 0) + 1

        # Distribución por formato
        by_format = {}
        for item in history:
            fmt = item.get('file_format', 'unknown')
            by_format[fmt] = by_format.get(fmt, 0) + 1

        # Actividad reciente (últimas 10)
        recent_activity = []
        for item in history[:10]:
            recent_activity.append({
                "name": item.get('name', 'Unknown'),
                "status": item.get('status', 'unknown'),
                "records": item.get('completed_records', 0),
                "end_time": item.get('end_time', '')
            })

        return {
            "total_simulations": total_simulations,
            "total_records": total_records,
            "avg_duration": avg_duration,
            "by_status": by_status,
            "by_format": by_format,
            "recent_activity": recent_activity
        }

    @app.get("/api/files", response_model=FileListResponse, tags=[tag_files],
             summary=endpoints["list_files"]["summary"], description=endpoints["list_files"]["desc"])
    def list_files(current_user: str = Depends(get_current_user)):
        if not os.path.exists(Config.DATA_DIR):
            return {"files": []}
        all_files = os.listdir(Config.DATA_DIR)
        prefix = f"{current_user}__"
        visible_files = [f for f in all_files if not f.startswith('.') and f.startswith(prefix)]
        visible_files = [f[len(prefix):] for f in visible_files]
        visible_files.sort(reverse=True)
        return {"files": visible_files}

    @app.get("/api/files/download/{filename}", tags=[tag_files],
             summary=endpoints["download"]["summary"], description=endpoints["download"]["desc"])
    def download_file(filename: str, current_user: str = Depends(get_current_user_for_download)):
        path = os.path.join(Config.DATA_DIR, f"{current_user}__{filename}")
        if os.path.exists(path):
            return FileResponse(path, filename=filename)
        raise HTTPException(status_code=404, detail=endpoints["download"]["error_404"])

    @app.post("/api/ai/generate-schema", response_model=AISchemaResponse, tags=["AI Assistant"],
              summary="Generar esquema con IA / Generate schema with AI",
              description="Utiliza GROQ AI para generar automáticamente un esquema de datos basado en la descripción / Uses GROQ AI to automatically generate a data schema based on description")
    def generate_schema_with_ai(request: AISchemaRequest, current_user: str = Depends(get_current_user)):
        if not Groq:
            raise HTTPException(status_code=500, detail="GROQ library not installed")

        if not Config.GROQ_API_KEY:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in environment variables")

        try:
            client = Groq(api_key=Config.GROQ_API_KEY)

            prompt = f"""Eres un asistente experto en diseño de datos sintéticos. Genera un esquema JSON para simular datos basándote en esta descripción:

"{request.description}"

Debes responder ÚNICAMENTE con un objeto JSON válido con esta estructura exacta (sin markdown, sin explicaciones):
{{
  "simulation_name": "nombre descriptivo para la simulación",
  "suggested_records": número_de_registros_sugerido,
  "suggested_target_type": "file|mqtt|kafka|http|rabbitmq|postgres|mongodb|mysql",
  "suggested_sink_config": {{
    "file_format": "json|csv|xml|toml|toon",
    "mqtt_host": "...",
    "mqtt_topic": "...",
    "kafka_bootstrap": "...",
    "kafka_topic": "...",
    "http_url": "...",
    "rabbitmq_host": "...",
    "rabbitmq_queue": "...",
    "postgres_host": "...",
    "postgres_port": 5432,
    "postgres_db": "...",
    "postgres_user": "...",
    "postgres_table": "...",
    "mongodb_uri": "mongodb://localhost:27017",
    "mongodb_db": "...",
    "mongodb_collection": "...",
    "mysql_host": "...",
    "mysql_port": 3306,
    "mysql_db": "...",
    "mysql_user": "...",
    "mysql_table": "..."
  }},
  "schema_fields": [
    {{
      "name": "nombre_campo",
      "type": "tipo_campo",
      "min": valor_minimo (solo para int/float),
      "max": valor_maximo (solo para int/float),
      "options": ["opcion1", "opcion2"] (solo para choice),
      "null_percentage": 0,
      "base_value": 50,
      "trend_slope": 0.1,
      "seasonal_amplitude": 5,
      "seasonal_period": 24,
      "noise_level": 1
    }}
  ]
}}

Tipos disponibles: "int", "float", "name", "email", "city", "country", "phone", "address", "company", "job", "ip_address", "latitude", "longitude", "credit_card", "iban", "url", "choice", "datetime", "uuid", "timeseries"

Si no hay contexto técnico de integración, usa "suggested_target_type": "file" y "file_format": "json".
Solo incluye en suggested_sink_config los campos relevantes para el target elegido.

Ejemplos:
- Para temperatura: {{"name": "temperatura", "type": "float", "min": 20, "max": 80, "null_percentage": 0}}
- Para estado: {{"name": "estado", "type": "choice", "options": ["ON", "OFF", "STANDBY"], "null_percentage": 0}}
- Para nombre: {{"name": "nombre", "type": "name", "null_percentage": 0}}

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""

            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=2048,
            )

            response_text = chat_completion.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse the JSON response
            schema_data = json.loads(response_text)
            allowed_targets = {"file", "mqtt", "kafka", "http", "rabbitmq", "postgres", "mongodb", "mysql"}
            suggested_target = schema_data.get("suggested_target_type", "file")
            if suggested_target not in allowed_targets:
                suggested_target = "file"
            suggested_sink_config = schema_data.get("suggested_sink_config", {})
            if not isinstance(suggested_sink_config, dict):
                suggested_sink_config = {}

            return AISchemaResponse(
                schema_fields=schema_data["schema_fields"],
                simulation_name=schema_data.get("simulation_name", "AI_Generated_Simulation"),
                suggested_records=schema_data.get("suggested_records", 100),
                suggested_target_type=suggested_target,
                suggested_sink_config=suggested_sink_config
            )

        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Error parsing AI response: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error calling GROQ API: {str(e)}")

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
