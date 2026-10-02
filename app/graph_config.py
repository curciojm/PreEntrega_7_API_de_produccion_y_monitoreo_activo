from typing import Literal

from langgraph.graph import StateGraph, START, END

from agents.profesor import nodo_profesor
from agents.supervisor import nodo_supervisor
from agents.evaluador import nodo_evaluador
from agents.sintesis import nodo_sintesis
from schemas import AgentState


def enrutar(
    state: AgentState,
) -> Literal["profesor", "evaluador", "sintesis"]:

    if state["next_agent"] == "FINISH":
        return "sintesis"

    return state["next_agent"]


grafo = StateGraph(AgentState)

grafo.add_node("supervisor", nodo_supervisor)
grafo.add_node("profesor", nodo_profesor)
grafo.add_node("evaluador", nodo_evaluador)
grafo.add_node("sintesis", nodo_sintesis)

grafo.add_edge(START, "supervisor")

grafo.add_conditional_edges(
    "supervisor",
    enrutar,
    {
        "profesor": "profesor",
        "evaluador": "evaluador",
        "sintesis": "sintesis",
    },
)

grafo.add_edge("profesor", "supervisor")
grafo.add_edge("evaluador", "supervisor")

grafo.add_edge("sintesis", END)