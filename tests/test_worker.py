import json
from unittest.mock import AsyncMock, patch

import pytest

from app.worker import procesar_aprobacion


@pytest.mark.asyncio
async def test_procesar_aprobacion_marca_failed_si_falla_el_grafo():

    job_id = "test-job-123"

    task_data = {
        "job_id": job_id,
        "query": "Evaluar una respuesta sobre la media.",
        "status": "waiting_approval",
        "result": None,
        "error": None,
    }

    approval_data = {
        "decision": "approve",
        "feedback": "",
    }

    fake_redis = AsyncMock()

    # GET del estado de la tarea
    # GET de la aprobación
    fake_redis.get.side_effect = [
        json.dumps(task_data),
        json.dumps(approval_data),
    ]

    # Mock del grafo: falla al intentar continuar
    fake_app = AsyncMock()
    fake_app.ainvoke.side_effect = Exception(
        "Error simulado del grafo"
    )

    with patch(
        "app.worker.redis_client",
        fake_redis,
    ):
        await procesar_aprobacion(
            job_id,
            fake_app,
        )

    # Verificamos que se actualizó el estado a failed
    llamadas_set = fake_redis.set.await_args_list

    ultima_llamada = llamadas_set[-1]

    key_guardada = ultima_llamada.args[0]
    datos_guardados = json.loads(
        ultima_llamada.args[1]
    )

    assert key_guardada == f"task_status:{job_id}"
    assert datos_guardados["status"] == "failed"
    assert datos_guardados["result"] is None
    assert datos_guardados["error"] == "Error simulado del grafo"

    # Verificamos que efectivamente se intentó ejecutar el grafo
    fake_app.ainvoke.assert_awaited_once()