# API de producción y monitoreo activo (Pre-Entrega 7)

Este proyecto corresponde a la **Pre-Entrega 7 del curso de AI Engineering**.

La entrega consiste en exponer mediante una API REST asíncrona el sistema multi-agente desarrollado en la Pre-Entrega 6, incorporando una arquitectura orientada a producción mediante **FastAPI + Redis + Worker + LangGraph**, persistencia del estado y checkpoints, observabilidad con **Arize Phoenix**, métricas de costo y latencia, y un flujo de **Human-in-the-loop (HITL)**.

**Link video de explicación del flujo de ejecución y Human-in-the-loop:**  
[Video de explicación](https://drive.google.com/file/d/1vc6fj9Q3QblrYEaXFmkpFuMy8TkhwZRh/view?usp=drive_link)

---

## Descripción

La aplicación expone una **API REST asíncrona** que permite enviar tareas al sistema multi-agente sin bloquear la solicitud HTTP mientras se ejecuta el procesamiento.

La arquitectura separa la recepción de solicitudes de la ejecución del sistema multi-agente:

```text
Cliente
   │
   │ POST /process
   ▼
FastAPI
   │
   │ job_id
   ▼
Redis Queue
   │
   ▼
Worker
   │
   ▼
LangGraph
   │
   ├── Supervisor
   │      ├── Profesor
   │      └── Evaluador
   │
   ├── Human-in-the-loop
   │
   └── Síntesis
```

De esta manera, el endpoint HTTP recibe la tarea, genera un identificador y la coloca en una cola de Redis. El procesamiento pesado queda a cargo de un Worker independiente.

La aplicación utiliza:

- **FastAPI** para la API REST.
- **Redis** para la cola de tareas y la persistencia del estado.
- **LangGraph** para la orquestación del sistema multi-agente.
- **Redis Checkpointer** para persistir el estado del grafo.
- **Worker asíncrono** para ejecutar las tareas fuera del contexto de la solicitud HTTP.
- **Human-in-the-loop** mediante `interrupt()` y `Command(resume=...)`.
- **Arize Phoenix + OpenInference** para observabilidad.
- **Trazas JSON** para conservar el detalle de las ejecuciones.
- Manejo de errores de ejecución y actualización del estado de las tareas a `FAILED`.

---

## Correspondencia entre requisitos y componentes

| Requisito | Implementación |
|---|---|
| API REST asíncrona | `app/main.py` |
| Crear tarea | `POST /process` |
| Consultar estado | `GET /status/{job_id}` |
| Aprobación humana | `POST /approve/{job_id}` |
| Cola principal | Redis `multiagent_tasks` |
| Cola de aprobaciones | Redis `multiagent_approvals` |
| Estado de tareas | Redis `task_status:{job_id}` |
| Worker | `app/worker.py` |
| Grafo multi-agente | `app/graph_config.py` |
| Checkpoints | `AsyncRedisSaver` |
| Human-in-the-loop | `app/hitl.py` |
| Observabilidad | `app/observability.py` |
| Instrumentación | OpenInference + Phoenix |
| Trazas detalladas | `traces/` |
| Evidencia de observabilidad | `screenshots/` |
| Manejo de errores | `app/errors.py` |
| Modelos y estado | `app/schemas.py` |
| Serialización de trazas | `app/trace_utils.py` |

---

# Arquitectura

El flujo general comienza cuando el cliente realiza un `POST /process`.

```text
Usuario
   │
   ▼
POST /process
   │
   ▼
FastAPI
   │
   ├── genera job_id
   ├── guarda estado inicial en Redis
   └── agrega job_id a multiagent_tasks
              │
              ▼
         Redis Queue
              │
              ▼
            Worker
              │
              ▼
          LangGraph
              │
       ┌──────┴──────┐
       ▼             ▼
  Supervisor      Supervisor
       │             │
   Profesor       Evaluador
       │             │
       └──────┬──────┘
              ▼
           Síntesis
              │
              ▼
             DONE
```

El endpoint no permanece esperando a que termine el procesamiento multi-agente. Devuelve inmediatamente el `job_id`, que posteriormente puede utilizarse para consultar el estado de la tarea.

---

## Flujo Human-in-the-loop

Cuando el Supervisor determina que debe utilizarse el agente evaluador, el flujo pasa previamente por el nodo de aprobación humana.

```text
Supervisor
    │
    ▼
Human Approval
    │
    ▼
interrupt()
    │
    ▼
WAITING_APPROVAL
    │
    │ POST /approve/{job_id}
    ▼
Redis
    │
    ▼
Worker
    │
    ▼
Command(resume=...)
    │
    ▼
Evaluador
    │
    ├── revisión necesaria ──► Human Approval
    │
    └── evaluación final ───► Supervisor
                                  │
                                  ▼
                               Síntesis
                                  │
                                  ▼
                                 DONE
```

El flujo utiliza `interrupt()` para pausar la ejecución del grafo y `Command(resume=...)` para continuarla una vez recibida la decisión humana.

La intervención humana puede:

- **Aprobar** la evaluación y continuar el flujo.
- **Rechazar** la evaluación proporcionando feedback para que el evaluador vuelva a analizar la respuesta.

El feedback humano se incorpora a la siguiente evaluación y se persiste junto con los demás eventos de intervención.

---

# API

## `POST /process`

Recibe una consulta y crea una nueva tarea.

El endpoint:

1. Genera un `job_id`.
2. Guarda el estado inicial en Redis.
3. Agrega el `job_id` a la cola `multiagent_tasks`.
4. Devuelve inmediatamente el identificador de la tarea.

Ejemplo conceptual:

```json
{
    "query": "Quiero que evalúes mi respuesta sobre la media..."
}
```

Respuesta:

```json
{
    "job_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "status": "pending"
}
```

---

## `GET /status/{job_id}`

Permite consultar el estado de una tarea.

Los principales estados utilizados son:

```text
pending
running
waiting_approval
done
failed
```

El estado se almacena en Redis mediante la clave:

```text
task_status:{job_id}
```

Además del estado, se conserva información sobre la consulta, resultado y posibles errores.

---

## `POST /approve/{job_id}`

Permite responder a una solicitud de aprobación humana.

Ejemplo de aprobación:

```json
{
    "decision": "approve",
    "feedback": ""
}
```

Ejemplo de rechazo:

```json
{
    "decision": "reject",
    "feedback": "Revisá la explicación y agregá un ejemplo aplicado a una investigación psicológica."
}
```

El endpoint no reanuda directamente el grafo. Guarda la decisión en Redis y la coloca en la cola `multiagent_approvals`.

El Worker recupera posteriormente la aprobación y continúa la ejecución de LangGraph.

---

# Procesamiento asíncrono

La separación entre FastAPI y Worker permite desacoplar la recepción de las solicitudes de la ejecución del sistema multi-agente.

El flujo es:

```text
POST /process
      │
      ▼
Redis
      │
      ▼
multiagent_tasks
      │
      ▼
Worker
      │
      ▼
LangGraph
```

FastAPI funciona como productor de tareas y el Worker como consumidor.

La cola principal utiliza:

```python
RPUSH
LPOP
```

De esta forma, el endpoint HTTP no queda bloqueado esperando la finalización de los agentes.

---

# Redis

Redis cumple varias funciones dentro de la aplicación.

## Estado de las tareas

Cada tarea utiliza una clave:

```text
task_status:{job_id}
```

El estado contiene información como:

```json
{
    "job_id": "...",
    "query": "...",
    "status": "running",
    "result": null,
    "error": null
}
```

Si ocurre una excepción durante la ejecución en segundo plano, el Worker actualiza el estado de la tarea a:

```text
failed
```

Esto evita que una tarea quede indefinidamente en estado `running`.

## Colas

Se utilizan dos colas principales:

```text
multiagent_tasks
multiagent_approvals
```

La primera contiene las tareas nuevas y la segunda las decisiones de aprobación humana.

## Checkpoints

El grafo de LangGraph se compila utilizando `AsyncRedisSaver`:

```python
async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
    app = grafo.compile(checkpointer=checkpointer)
```

Esto permite persistir el estado del grafo y continuar la ejecución después de una interrupción provocada por el flujo HITL.

---

# Worker

El Worker es responsable de consumir las tareas de Redis y ejecutar el sistema multi-agente.

El flujo general es:

```text
Redis Queue
    │
    ▼
Worker
    │
    ├── status = RUNNING
    │
    ▼
LangGraph
    │
    ├── WAITING_APPROVAL
    │
    └── DONE
```

Si ocurre una excepción durante el procesamiento:

```text
Exception
    │
    ▼
status = FAILED
```

Los errores quedan registrados y pueden consultarse mediante el endpoint de estado.

---

# Sistema multi-agente

El sistema mantiene la arquitectura desarrollada en la Pre-Entrega 6.

Está compuesto por:

- `agente_profesor`
- `agente_evaluador`
- `nodo_supervisor`
- `nodo_sintesis`

El estado compartido se define mediante `AgentState`.

El Supervisor decide qué especialista debe intervenir:

```text
Supervisor
    │
    ├── profesor
    │
    ├── evaluador
    │
    └── FINISH
```

Cuando corresponde finalizar, el flujo pasa al nodo de síntesis.

---

# Supervisor

El Supervisor utiliza un modelo LLM con salida estructurada mediante `DecisionSupervisor`.

Las opciones posibles son:

```text
profesor
evaluador
FINISH
```

El Supervisor analiza la consulta y las contribuciones acumuladas para determinar qué agente debe intervenir.

También se utiliza un límite máximo de pasos:

```python
MAX_PASOS = 6
```

Esto permite evitar ciclos excesivos en el grafo.

El sistema utiliza fallback entre proveedores LLM:

```text
OpenAI
   ↓
Anthropic
   ↓
Gemini
```

Si un proveedor falla, se intenta continuar con el siguiente.

---

# Human-in-the-loop

La aprobación humana se implementa mediante el mecanismo de interrupción de LangGraph.

El nodo utiliza:

```python
interrupt(...)
```

Cuando se ejecuta, el grafo queda pausado y la tarea pasa a:

```text
waiting_approval
```

Posteriormente, el endpoint:

```text
POST /approve/{job_id}
```

recibe la decisión humana.

El Worker recupera la decisión y utiliza:

```python
Command(
    resume={
        "decision": decision,
        "feedback": feedback,
    }
)
```

para continuar la ejecución.

## Rechazo y reevaluación

Cuando el usuario rechaza la evaluación, el feedback se incorpora a la siguiente ejecución del evaluador.

Por ejemplo:

```text
"Revisá la explicación y aclarale que la media no necesariamente
coincide con el valor central de los datos ordenados. Agregá un
ejemplo aplicado a una investigación psicológica con participantes humanos."
```

El evaluador vuelve a utilizar sus herramientas y realiza una nueva evaluación considerando la revisión humana.

Si la evaluación vuelve a requerir intervención, el grafo puede regresar nuevamente a `human_approval`.

---

# Persistencia de las intervenciones humanas

Las decisiones humanas se almacenan temporalmente en Redis mediante:

```text
human_events:{job_id}
```

Cada evento contiene información como:

```json
{
    "tipo": "HumanApproval",
    "decision": "reject",
    "feedback": "..."
}
```

Al finalizar la tarea, estos eventos se incorporan a la traza JSON correspondiente.

De esta manera, la intervención humana forma parte del registro de ejecución de la tarea.

---

# Observabilidad

La aplicación utiliza **Arize Phoenix** junto con **OpenInference** para instrumentar el sistema.

La instrumentación se configura mediante:

```python
LangChainInstrumentor().instrument(
    tracer_provider=tracer_provider
)
```

Phoenix recibe las trazas mediante:

```text
http://localhost:6006/v1/traces
```

y la interfaz web está disponible en:

```text
http://localhost:6006
```

Las capturas almacenadas en `screenshots/` muestran la observabilidad de las ejecuciones, incluyendo:

- trazas;
- spans;
- secuencia de ejecución;
- componentes involucrados;
- latencia;
- costo;
- ejecución concurrente;
- flujo Human-in-the-loop.

Las trazas detalladas se conservan adicionalmente en formato JSON dentro de `traces/`.

---

# Trazas detalladas

Cada ejecución genera una traza JSON con información sobre el flujo observable de la aplicación.

Las trazas pueden contener:

- mensajes del usuario;
- respuestas de los agentes;
- llamadas a herramientas;
- resultados de herramientas;
- agentes involucrados;
- decisiones del workflow;
- intervenciones humanas;
- eventos de aprobación;
- feedback humano.

Las trazas representan la **ejecución observable del sistema**, no el razonamiento interno no observable de los modelos.

Una ejecución con Human-in-the-loop puede generar diferentes etapas observables debido al mecanismo de `interrupt()` y `resume()`:

```text
Ejecución inicial
      │
      ▼
Evaluador
      │
      ▼
Human Approval
      │
      ▼
interrupt()
      │
      ▼
Resume con feedback
      │
      ▼
Nueva evaluación
      │
      ▼
Human Approval
      │
      ▼
interrupt()
      │
      ▼
Resume con aprobación
      │
      ▼
Síntesis
      │
      ▼
DONE
```

---

# Prueba con cinco solicitudes concurrentes

Se realizaron cinco solicitudes concurrentes mediante `POST /process`.

Cada solicitud recibió un `job_id` independiente y fue procesada mediante la cola de Redis y el Worker.

La corrida se utilizó como base para obtener las métricas de:

- costo por ejecución;
- costo de tokens de entrada y salida;
- latencia;
- p95 de latencia.

Las capturas correspondientes se encuentran en:

```text
screenshots/
```

Las cinco ejecuciones también cuentan con sus respectivas trazas detalladas en:

```text
traces/
```

---

# Costo por ejecución

El costo se calculó a partir de los tokens de entrada y salida registrados durante las ejecuciones.

La evidencia de la corrida concurrente se encuentra en:

```text
screenshots/trace_plot_cost.png
```

La captura permite comparar el costo correspondiente a las cinco ejecuciones solicitadas.

### Trazas de mayor costo

Dentro de la corrida, las dos ejecuciones de mayor costo fueron:

**Evaluar conceptualización de muestreo aleatorio**

- Costo total: **USD 0.0052**
- Input: **USD 0.0034**
- Output: **USD 0.0017**

**Evaluar conceptualización de regresión**

- Costo total: **USD 0.0040**
- Input: **USD 0.0026**
- Output: **USD 0.0014**

El detalle de estas ejecuciones se encuentra en las trazas JSON correspondientes dentro de:

```text
traces/
```

---

# Latencia y p95

El análisis de latencia se realizó sobre las cinco ejecuciones concurrentes.

La evidencia correspondiente se encuentra en:

```text
screenshots/trace_plot_latency.png
screenshots/trace_plot_latency_values.png
```

Las capturas muestran la distribución de latencia de las ejecuciones y el cálculo del percentil 95.

El **p95** permite observar una estimación de la latencia que no es superada por aproximadamente el 95 % de las solicitudes de la corrida analizada.

---

# Manejo de errores

La API y el Worker cuentan con manejo de errores para evitar que una excepción durante una ejecución deje la tarea indefinidamente en estado `running`.

Los errores de los proveedores LLM se clasifican mediante `errors.py`:

```text
RATE_LIMIT
KEY
UNKNOWN
```

El sistema también implementa fallback entre proveedores:

```text
OpenAI
   ↓
Anthropic
   ↓
Gemini
```

Si todos los proveedores disponibles fallan, la excepción se propaga al Worker, que actualiza el estado de la tarea a:

```text
FAILED
```

El error queda disponible mediante:

```text
GET /status/{job_id}
```

---

# Requisitos

Para ejecutar el proyecto se requiere:

- Python 3.12+ según los requisitos de la entrega.
- Redis.
- Google Gemini API key.
- Pinecone API key e índice.
- Arize Phoenix.
- Opcionalmente, claves de OpenAI y Anthropic para el fallback.

Durante el desarrollo se utilizó Python 3.11.x debido a incompatibilidades de algunas dependencias del entorno de desarrollo.

---

# Instalación

Crear el entorno virtual:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

En Linux/macOS:

```bash
source .venv/bin/activate
```

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

---

# Redis

La aplicación utiliza:

```text
redis://localhost:6379
```

Si se utiliza un contenedor Docker previamente creado:

```bash
docker start redis
```

Para comprobar que Redis está disponible:

```bash
docker exec -it redis redis-cli ping
```

La respuesta esperada es:

```text
PONG
```

---

# Variables de entorno

Crear un archivo `.env` a partir de `.env.example`.

Las variables utilizadas son:

```text
GOOGLE_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
PINECONE_API_KEY=
INDEX_NAME=
REDIS_URL=
```

Las claves reales no se incluyen en el repositorio.

---

# Ejecución

## Phoenix

Iniciar Arize Phoenix antes de ejecutar el Worker.

La interfaz estará disponible en:

```text
http://localhost:6006
```

## API

Iniciar FastAPI:

```bash
uvicorn app.main:app --reload
```

La API estará disponible en:

```text
http://localhost:8000
```

La documentación interactiva puede consultarse en:

```text
http://localhost:8000/docs
```

## Worker

En otra terminal:

```bash
python -m app.worker
```

Para ejecutar correctamente el sistema deben permanecer disponibles simultáneamente:

```text
Redis
Phoenix
FastAPI
Worker
```

---

# Ejemplo de ejecución Human-in-the-loop

Una consulta utilizada para probar el flujo fue:

```text
Quiero que evalúes mi respuesta sobre la media:

La media es el promedio de un conjunto de valores. Se calcula sumando
todos los valores y dividiendo el resultado por la cantidad de valores.
Por ejemplo, si cinco estudiantes obtienen 4, 5, 6, 7 y 8 en una prueba,
la media es 6. La media sirve para conocer cuál es el valor que se
encuentra en el centro de los datos.
```

El flujo produce inicialmente un estado:

```text
waiting_approval
```

Posteriormente se envió un rechazo con el siguiente feedback:

```text
Revisá la explicación y aclarale que la media no necesariamente coincide
con el valor central de los datos ordenados. Agregá un ejemplo aplicado
a una investigación psicológica con participantes humanos.
```

El evaluador vuelve a analizar la respuesta considerando el feedback recibido.

Finalmente se envía una aprobación:

```json
{
    "decision": "approve",
    "feedback": ""
}
```

y la tarea continúa hasta finalizar:

```text
DONE
```

---

# Tecnologías utilizadas

- Python
- FastAPI
- Uvicorn
- asyncio
- Pydantic
- Redis
- LangChain
- LangChain Core
- LangGraph
- LangGraph Checkpoint Redis
- Google GenAI
- OpenAI
- Anthropic
- Pinecone
- Hugging Face
- Sentence Transformers
- scikit-learn
- BM25
- tiktoken
- Arize Phoenix
- OpenInference
- OpenTelemetry
- Pandas
- Git

---

# Estructura del proyecto

```text
├── app/
│   ├── __init__.py
│   ├── chunking.py
│   ├── db_config.py
│   ├── db_ingest.py
│   ├── errors.py
│   ├── main.py
│   ├── models.py
│   ├── worker.py
│   ├── graph_config.py
│   ├── schemas.py
│   ├── errors.py
│   ├── logging_config.py
│   ├── trace_utils.py
│   ├── hitl.py
│   ├── observability.py
│   ├── retriever.py
│   ├── redis.py
│   ├── setup.py
│   ├── tools.py
│   └── agents/
│       ├── profesor.py
│       ├── evaluador.py
│       ├── supervisor.py
│       └── sintesis.py
├── data/
├── traces/
│   └── *.json
├── screenshots/
│   ├── [capturas de trazas]
│   ├── trace_plot_cost.png
│   ├── trace_plot_latency.png
│   └── trace_plot_latency_values.png
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

# Calidad y decisiones de diseño

El proyecto incorpora las siguientes decisiones orientadas a una implementación más cercana a producción:

- Uso de `async/await` para las operaciones de I/O.
- Separación entre API y Worker.
- Redis como mecanismo de desacoplamiento entre recepción y procesamiento.
- Persistencia del estado de las tareas.
- Estado explícito `FAILED` para errores de ejecución.
- Pydantic para validación de las solicitudes.
- `AgentState` para el estado compartido del grafo.
- Checkpoints persistentes mediante Redis.
- Human-in-the-loop mediante los mecanismos nativos de LangGraph.
- Variables de entorno para credenciales y configuración.
- Logging.
- Instrumentación mediante OpenTelemetry/OpenInference.
- Observabilidad con Arize Phoenix.
- Persistencia de trazas detalladas en JSON.
- Métricas de costo y latencia obtenidas sobre ejecuciones concurrentes.

Una decisión central de la arquitectura es evitar que el endpoint HTTP ejecute directamente las tareas pesadas del sistema multi-agente. FastAPI recibe y encola la tarea, mientras que el Worker se ocupa de ejecutar el grafo.

---

# Sobre el código

El desarrollo se realizó tomando como referencia los ejemplos y materiales proporcionados durante el curso, documentación oficial de las herramientas utilizadas, recursos disponibles en Internet y asistencia de ChatGPT para resolver dudas conceptuales, revisar implementaciones y depurar distintos problemas durante el desarrollo.