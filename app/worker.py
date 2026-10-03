import asyncio
import json

from redis import asyncio as aioredis
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command

from app.graph_config import grafo
from app.trace_utils import serializar_traza, guardar_traza


REDIS_URL = "redis://localhost:6379"
QUEUE_NAME = "multiagent_tasks"
STATUS_PREFIX = "task_status:"
APPROVAL_QUEUE = "multiagent_approvals"
APPROVAL_PREFIX = "approval_data:"


redis_client = aioredis.from_url(
    REDIS_URL,
    decode_responses=True
)

async def procesar_aprobacion(job_id, app):

    key = f"{STATUS_PREFIX}{job_id}"

    raw_data = await redis_client.get(key)

    if not raw_data:
        print(f"Job {job_id} no encontrado.")
        return

    task_data = json.loads(raw_data)

    if task_data["status"] != "waiting_approval":
        print(
            f"Job {job_id} no está esperando aprobación."
        )
        return

    config = {
        "configurable": {
            "thread_id": job_id
        },
        "recursion_limit": 10,
    }

    try:
        approval_key = f"{APPROVAL_PREFIX}{job_id}"

        raw_approval = await redis_client.get(
            approval_key
        )

        if not raw_approval:
            print(f"No hay datos de aprobación para {job_id}")
            return

        approval_data = json.loads(raw_approval)

        decision = approval_data["decision"]
        feedback = approval_data["feedback"]
        

        resultado = await app.ainvoke(
            Command(resume=True),
            config=config,
        )
        
        traza = serializar_traza(
            resultado["messages"]
        )

        guardar_traza(
            traza,
            job_id
        )

        response = resultado["messages"][-1].content

        task_data["status"] = "completed"
        task_data["result"] = response
        task_data["error"] = None

        await redis_client.delete(
        approval_key
        )

    except Exception as e:

        task_data["status"] = "failed"
        task_data["result"] = None
        task_data["error"] = str(e)

    await redis_client.set(
        key,
        json.dumps(task_data)
    )

    print(f"Job {job_id} reanudado y finalizado.")


async def main_worker():

    print("Worker iniciado y escuchando...")

    async with AsyncRedisSaver.from_conn_string(
        REDIS_URL
    ) as checkpointer:

        app = grafo.compile(
            checkpointer=checkpointer
        )

        while True:

            # ==========================================
            # 1. JOBS NUEVOS
            # ==========================================

            job_id = await redis_client.lpop(
                QUEUE_NAME
            )

            if job_id is not None:

                print(
                    f"Procesando Job: {job_id}"
                )

                key = f"{STATUS_PREFIX}{job_id}"

                raw_data = await redis_client.get(key)

                if not raw_data:
                    print(
                        f"Job {job_id} no encontrado."
                    )
                    continue

                task_data = json.loads(raw_data)

                task_data["status"] = "processing"

                await redis_client.set(
                    key,
                    json.dumps(task_data)
                )

                consulta = task_data["query"]

                config = {
                    "configurable": {
                        "thread_id": job_id
                    },
                    "recursion_limit": 10,
                }

                try:

                    resultado = await app.ainvoke(
                        {
                            "messages": [
                                HumanMessage(
                                    content=consulta
                                )
                            ],
                            "job_id": job_id,
                        },
                        config=config,
                    )

                    if "__interrupt__" in resultado:

                        task_data["status"] = (
                            "waiting_approval"
                        )
                        task_data["result"] = None
                        task_data["error"] = None

                        print(
                            f"Job {job_id} "
                            "esperando aprobación humana."
                        )

                    else:

                        traza = serializar_traza(
                            resultado["messages"]
                        )

                        guardar_traza(
                            traza,
                            job_id
                        )

                        response = (
                            resultado["messages"][-1]
                            .content
                        )

                        task_data["status"] = (
                            "completed"
                        )
                        task_data["result"] = response
                        task_data["error"] = None

                except Exception as e:

                    task_data["status"] = "failed"
                    task_data["result"] = None
                    task_data["error"] = str(e)

                await redis_client.set(
                    key,
                    json.dumps(task_data)
                )

                print(
                    f"Job {job_id} finalizado."
                )

                continue

            # ==========================================
            # 2. APROBACIONES HUMANAS
            # ==========================================

            approval_job_id = await redis_client.lpop(
                APPROVAL_QUEUE
            )

            if approval_job_id is not None:

                print(
                    "Procesando aprobación del "
                    f"Job: {approval_job_id}"
                )

                await procesar_aprobacion(
                    approval_job_id,
                    app
                )

                continue

            # ==========================================
            # 3. NADA PARA PROCESAR
            # ==========================================

            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main_worker())