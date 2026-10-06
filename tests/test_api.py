import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_task():
    fake_redis = AsyncMock()

    with patch("app.main.redis_client", fake_redis):
        response = client.post(
            "/process",
            json={
                "query": "Explicá qué es la media."
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert "job_id" in data
    assert data["status"] == "pending"

    fake_redis.set.assert_awaited_once()
    fake_redis.rpush.assert_awaited_once()

    # Verificar que se encoló el job en la cola correcta
    args = fake_redis.rpush.await_args.args

    assert args[0] == "multiagent_tasks"
    assert args[1] == data["job_id"]

    # Verificar que se guardó el estado inicial
    set_args = fake_redis.set.await_args.args

    assert set_args[0].startswith("task_status:")

    task_data = json.loads(set_args[1])

    assert task_data["job_id"] == data["job_id"]
    assert task_data["query"] == "Explicá qué es la media."
    assert task_data["status"] == "pending"