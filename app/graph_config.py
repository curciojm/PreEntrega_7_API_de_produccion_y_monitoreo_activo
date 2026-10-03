from typing import Literal

from langgraph.graph import StateGraph, START, END
from app.hitl import human_approval

from app.agents.profesor import nodo_profesor
from app.agents.supervisor import nodo_supervisor
from app.agents.evaluador import nodo_evaluador
from app.agents.sintesis import nodo_sintesis
from app.schemas import AgentState


def enrutar(
    state: AgentState,
) -> Literal["profesor", "evaluador", "sintesis"]:

    if state["next_agent"] == "FINISH":
        return "sintesis"

    return state["next_agent"]

def enrutar_aprobacion(
    state: AgentState,
) -> Literal["evaluador", "sintesis"]:
    # if true va al evaluador
    if state["approval"]:
        return "evaluador"

    return "evaluador"

grafo = StateGraph(AgentState)

grafo.add_node("supervisor", nodo_supervisor)
grafo.add_node("profesor", nodo_profesor)
grafo.add_node("evaluador", nodo_evaluador)
grafo.add_node("sintesis", nodo_sintesis)
grafo.add_node("human_approval", human_approval) # agregamos human approval al grafo

grafo.add_edge(START, "supervisor")

grafo.add_conditional_edges(
    "supervisor",
    enrutar,
    {
        "profesor": "profesor",
        "evaluador": "human_approval", # agregamos la aprobacion humana luego de la evaluacion
        "sintesis": "sintesis",
    },
)

grafo.add_edge("profesor", "supervisor")

grafo.add_conditional_edges(
    "human_approval",
    enrutar_aprobacion,
    {
        "evaluador": "evaluador",
        "sintesis": "sintesis",
    },
)
grafo.add_edge("evaluador", "supervisor")

grafo.add_edge("sintesis", END)