import asyncio
import uuid
import json
import uvicorn

from fastapi import FastAPI, HTTPException
from redis import asyncio as aioredis
from pydantic import BaseModel
from schemas import TaskResponse, TaskRequest

# --- CONFIGURACIÓN ---
REDIS_URL = "redis://localhost:6379"
QUEUE_NAME = "multiagent_tasks"
STATUS_PREFIX = "task_status:"

# Nombre que va a llevar mi api.
app = FastAPI(title="PreEntrega 7 - Multi-Agent API")

# Decode true: Cuando Redis me devuelva datos, conviértelos de bytes a str de Python,
# caso contrario lo guarda en bytes
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

# --- ENDPOINTS API ---

# @app.post es un decorador de FastAPI. Cuando llegue una petición HTTP POST
# a /algo, ejecutá la función que está debajo.
# El código parece simular una query de estado pendiente, asincrónica por supuesto.
@app.post("/process", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """
    Recibe una solicitud, genera un job_id y encola la tarea en Redis.
    """
    job_id = str(uuid.uuid4())  # Generación de identificador único aleatorio

    # Definir el estado inicial
    task_data = {
        "job_id": job_id,
        "query": request.query,
        # pending es lo que va a tener por default. Si se hace algo, se modifica por supuesto. ej task_data["status"] = "failed"
        "status": "pending",
        "result": None,
        "error": None
    }

    # 1. Guardar estado inicial en Redis
    await redis_client.set(
        f"{STATUS_PREFIX}{job_id}",
        json.dumps(task_data)
    )

    # 2. Encolar el job_id para que el worker lo procese
    # rpush significa Right Push: agrega un elemento al final de una lista de Redis.
    # Así FastAPI va agregando trabajos a la cola con rpush.
    # Esto permite que los trabajos se procesen en orden FIFO (First In, First Out):
    # el primero que entra es el primero que se procesa.
    await redis_client.rpush(QUEUE_NAME, job_id)

    return TaskResponse(job_id=job_id, status="pending")


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Consulta el estado actual de una tarea en Redis.
    """
    # Toma el status prefix
    data = await redis_client.get(f"{STATUS_PREFIX}{job_id}")

    if not data:
        raise HTTPException(status_code=404, detail="Job not found")

    return json.loads(data)

# --- EJECUCIÓN ---
# PYTHON 3.12
if __name__ == "__main__":

    # Uvicorn es un servidor ASGI, pensado especialmente para
    # aplicaciones modernas y asíncronas como FastAPI.
    #
    # Gunicorn es un servidor WSGI tradicional y, sobre todo,
    # un gestor de procesos/workers.

    # En producción, usarías procesos separados.
    # Aquí lanzamos el worker como tarea de fondo.

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
