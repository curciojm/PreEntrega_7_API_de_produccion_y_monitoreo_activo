import json
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage


def extraer_texto(mensaje) -> str:
    """Normaliza el contenido de un mensaje."""
    contenido = mensaje.content

    if isinstance(contenido, str):
        return contenido

    if isinstance(contenido, list):
        return "".join(
            bloque.get("text", "")
            for bloque in contenido if isinstance(bloque, dict)
        )

    return str(contenido)

def serializar_traza(mensajes) -> list[dict]:
    """Convierte los mensajes de LangGraph a un formato JSON simple."""
    traza = []

    for mensaje in mensajes:
        entrada = {
            "tipo": type(mensaje).__name__,
            "contenido": extraer_texto(mensaje),
        }

        if getattr(mensaje, "name", None):
            entrada["agente"] = mensaje.name

        if isinstance(mensaje, AIMessage) and mensaje.tool_calls:
            entrada["tool_calls"] = [
                {
                    "nombre": tool_call["name"],
                    "argumentos": tool_call["args"],
                }
                for tool_call in mensaje.tool_calls
            ]

        if isinstance(mensaje, ToolMessage):
            entrada["herramienta"] = mensaje.name

        traza.append(entrada)

    return traza

def guardar_traza(traza: list[dict], thread_id: str) -> None:
    """Guarda la traza ReAct de una conversación en formato JSON."""
    ruta = Path("traces") / f"{thread_id}.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(
            traza,
            archivo,
            ensure_ascii=False,
            indent=2,
        )