from langchain_core.messages import AIMessage, HumanMessage

from app.errors import classify_error
from app.logging_config import logger
from app.models import get_model
from app.schemas import AgentState




async def nodo_sintesis(state: AgentState) -> dict:

    contribuciones_texto = "\n".join(
        f"- [{c['agente']}] {c['aporte']}"
        for c in state.get("contribuciones", [])
    )

    pregunta_original = next(
        mensaje.content
        for mensaje in reversed(state["messages"])
        if isinstance(mensaje, HumanMessage)
    )

    prompt = (
        f"Pregunta original: {pregunta_original}\n\n"
        f"Aportes del equipo:\n{contribuciones_texto}\n\n"
        "Redactá una respuesta final clara y breve combinando "
        "los aportes relevantes del equipo. "
        "No menciones la arquitectura de agentes ni el proceso interno."
    )

    last_error = None

    for provider in ["openai", "anthropic", "gemini"]:
        try:
            logger.info(
                f"Intentando utilizar proveedor LLM para síntesis: {provider}"
            )

            llm = get_model(provider)
            respuesta_final = await llm.ainvoke(prompt)

            logger.info(
                f"Proveedor LLM utilizado correctamente para síntesis: {provider}"
            )

            return {
                "messages": [
                    AIMessage(
                        content=respuesta_final.content,
                        name="sintesis",
                    )
                ]
            }

        except Exception as e:
            last_error = e
            error = classify_error(e)

            logger.warning(
                f"El proveedor {provider} falló para síntesis: {error}"
            )

            continue

    raise classify_error(last_error)