from langgraph.types import interrupt


def human_approval(state):

    decision = interrupt(
        {
            "message": "Se requiere aprobación humana para ejecutar la evaluación.",
            "job_id": state["job_id"],
        }
    )

    return {
        "approval": decision["decision"] == "approve",
        "feedback_humano": decision.get("feedback", ""),
        "revisiones": state.get("revisiones", 0) + (
            1 if decision["decision"] == "reject" else 0
        )
    }