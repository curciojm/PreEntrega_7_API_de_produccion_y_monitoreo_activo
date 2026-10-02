import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from graph_config import grafo
from schemas import LLMError
from trace_utils import extraer_texto, guardar_traza, serializar_traza

CONSULTA_PROFESOR = """
¿Qué es la regresión?
"""

CONSULTA_EVALUADOR_MAL = """
Mi explicación sobre la regresión es:

"Una medida que se usa para ver si a partir del promedio se pueden obtener diferencias
entre dos grupos"
"""

CONSULTA_EVALUADOR_INCOMPLETA = """
Mi explicación sobre la regresión es:

"La regresión es una técnica que sirve para calcular promedios
y determinar si dos variables tienen una correlación."
"""

CONSULTA_EVALUADOR_BIEN = """
Mi explicación sobre la regresión es:

"La regresión es una técnica estadística que permite estudiar
la relación entre una variable y una o más variables. Permite cuantificar
cómo cambia, en promedio, la variable dependiente cuando
cambia una variable independiente"
"""

CONSULTA_EVALUADOR_MUY_BIEN = """
Mi explicación sobre la regresión es:

"La regresión es una técnica estadística que permite modelar
la relación entre una variable dependiente y una o más
variables independientes. En la regresión lineal se estima
una función que describe esa relación y permite cuantificar
cómo cambia, en promedio, la variable dependiente cuando
cambia una variable independiente. El modelo puede utilizarse
tanto para analizar la relación entre las variables como para
realizar predicciones. El criterio de ajuste de la recta utilizado es
el método de minímos cuadrados, l cual busca la línea que minimiza la suma 
de las diferencias al cuadrado entre los valores observados y los predichos."
"""

CONFIG = {
    "configurable": {
        "thread_id": "multiagente-1_evaluador_mal"
    },
    "recursion_limit": 10,
}


async def main():

    async with AsyncSqliteSaver.from_conn_string(
        "checkpoints.sqlite"
    ) as checkpointer:

        app = grafo.compile(checkpointer=checkpointer)

        consulta = CONSULTA_EVALUADOR_MAL

        print("=" * 80)
        print("🧑 SOLICITUD")
        print("=" * 80)
        print(consulta)

        try:
            resultado = await app.ainvoke(
                {
                    "messages": [
                        
                        HumanMessage(content=consulta)
                    ]
                },
                config=CONFIG,
            )

        except LLMError as e:
            print(f"\n❌ Error: {e}")
            return

        print("\n" + "=" * 80)
        print("🤖 RESPUESTA FINAL")
        print("=" * 80)
        print(
            extraer_texto(
                resultado["messages"][-1]
            )
        )

        traza = serializar_traza(
            resultado["messages"]
        )

        guardar_traza(
            traza,
            CONFIG["configurable"]["thread_id"],
        )

        print("\n" + "=" * 80)
        print("🔎 TRAZA")
        print("=" * 80)

        for paso in traza:
            print(paso)


if __name__ == "__main__":
    asyncio.run(main())