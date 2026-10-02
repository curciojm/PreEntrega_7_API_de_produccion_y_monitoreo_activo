import json

from redis import asyncio as aioredis
from langchain_core.messages import HumanMessage

from graph_config import grafo


REDIS_URL = "redis://localhost:6379"
QUEUE_NAME = "multiagent_tasks"
STATUS_PREFIX = "task_status:"

redis_client = aioredis.from_url(
    REDIS_URL,
    decode_responses=True
)


async def main_worker():
    """
    Loop infinito que procesa tareas de la cola de Redis.
    """

    print("Worker iniciado y escuchando...")

    while True:

        # Espera hasta que haya un job en la cola.
        result = await redis_client.blpop(
            QUEUE_NAME,
            timeout=0
        )

        if result:

            # Redis devuelve:
            # [nombre_de_la_cola, job_id]
            _, job_id = result

            print(f"Procesando Job: {job_id}")

            # -------------------------------------------------
            # 1. Obtener información del job
            # -------------------------------------------------

            key = f"{STATUS_PREFIX}{job_id}"

            raw_data = await redis_client.get(key)

            if not raw_data:
                print(f"Job {job_id} no encontrado.")
                continue

            task_data = json.loads(raw_data)

            # -------------------------------------------------
            # 2. Marcar como processing
            # -------------------------------------------------

            task_data["status"] = "processing"

            await redis_client.set(
                key,
                json.dumps(task_data)
            )

            # -------------------------------------------------
            # 3. Obtener consulta
            # -------------------------------------------------
            # ACA LOS THREADS
            consulta = task_data["query"]

            # Cada job tiene su propio thread_id.
            config = {
                "configurable": {
                    "thread_id": job_id
                },
                "recursion_limit": 10,
            }

            # -------------------------------------------------
            # 4. Ejecutar LangGraph
            # -------------------------------------------------

            try:
                # ACA SE EJECUTA LA CONSULTA
                resultado = await grafo.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content=consulta)
                        ]
                    },
                    config=config,
                )

                response = resultado["messages"][-1].content

                # -------------------------------------------------
                # 5. Marcar como completed
                # -------------------------------------------------

                task_data["status"] = "completed"
                task_data["result"] = response
                task_data["error"] = None

            except Exception as e:

                # -------------------------------------------------
                # 6. Si falla, marcar como failed
                # -------------------------------------------------

                task_data["status"] = "failed"
                task_data["result"] = None
                task_data["error"] = str(e)

            # -------------------------------------------------
            # 7. Guardar estado final
            # -------------------------------------------------

            await redis_client.set(
                key,
                json.dumps(task_data)
            )

            print(f"Job {job_id} finalizado.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main_worker())


## EL FLUJO COMPLETO ES:

# 1. FastAPI
#    │
#    │ recibe consulta
#    ↓
# 2. Redis
#    │
#    ├── guarda:
#    │     job_id
#    │     query
#    │     status = pending
#    │
#    └── mete job_id en la cola
#              │
#              ↓
# 3. Worker
#    │
#    ├── lee job_id de Redis
#    │
#    ├── lee los datos del job
#    │
#    ├── cambia status → processing
#    │
#    ↓
# 4. LangGraph
#    │
#    │ misma lógica de tu PE6
#    │
#    ├── Supervisor
#    ├── Agente profesor/evaluador
#    ├── herramientas
#    ├── Pinecone
#    └── LLM
#    │
#    ↓
# 5. Worker
#    │
#    ├── obtiene resultado
#    ├── status → completed
#    ├── guarda result
#    └── si falla → status = failed
#    │
#    ↓
# 6. Redis
#    │
#    └── guarda el estado final