import json
import uuid

from fastapi import FastAPI, HTTPException
from redis import asyncio as aioredis
from app.schemas import TaskResponse, TaskRequest

REDIS_URL = "redis://localhost:6379"
QUEUE_NAME = "multiagent_tasks"
STATUS_PREFIX = "task_status:"

app = FastAPI(title="PreEntrega 7 - Multi-Agent API")

redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

@app.post("/process", response_model=TaskResponse)
async def create_task(request: TaskRequest):
    """
    Recibe una solicitud, genera un job_id y encola la tarea en Redis.
    """
    job_id = str(uuid.uuid4())  # Generación de identificador único aleatorio

    task_data = {
        "job_id": job_id,
        "query": request.query,
        "status": "pending",
        "result": None,
        "error": None
    }

    await redis_client.set(
        f"{STATUS_PREFIX}{job_id}",
        json.dumps(task_data)
    )

    await redis_client.rpush(QUEUE_NAME, job_id)

    return TaskResponse(job_id=job_id, status="pending")


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Consulta el estado actual de una tarea en Redis.
    """
    data = await redis_client.get(f"{STATUS_PREFIX}{job_id}")

    if not data:
        raise HTTPException(status_code=404, detail="Job not found")

    return json.loads(data)