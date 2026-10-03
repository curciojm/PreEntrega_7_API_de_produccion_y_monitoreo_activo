from langgraph.types import interrupt


def human_approval(state):

    approval = interrupt(
        {
            "message": "Se requiere aprobación humana para ejecutar la evaluación.",
            "job_id": state["job_id"],
        }
    )

    return {
        "approval": approval
    }