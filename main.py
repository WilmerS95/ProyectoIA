import os
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv

load_dotenv()
clave_nvidia = os.getenv("NVIDIA_API_KEY")

os.environ["OPENAI_API_KEY"] = clave_nvidia
os.environ["OPENAI_API_BASE"] = "https://integrate.api.nvidia.com/v1"

llm_vision = "openai/meta/llama-3.2-11b-vision-instruct"
llm_grader = "openai/meta/llama-3.1-70b-instruct"
llm_reporter = "openai/meta/llama-3.1-8b-instruct"


agente_icr = Agent(
    role='Especialista en Reconocimiento Inteligente de Caracteres (ICR)',
    goal='Extraer con precisión el texto de exámenes manuscritos o impresos a partir de imágenes, identificando preguntas y respuestas.',
    backstory='Eres un experto en visión por computadora. Tu tarea es recibir imágenes digitalizadas de exámenes, leer la escritura de los estudiantes y estructurar el texto para que otros agentes puedan evaluarlo.',
    llm=llm_vision, # Ahora es un string válido para Pydantic
    verbose=True,
    allow_delegation=False
)

agente_rag = Agent(
    role='Investigador Académico',
    goal='Extraer y proporcionar el contexto exacto de los materiales didácticos del curso para evaluar el examen.',
    backstory='Eres un asistente de investigación impecable. Buscas en los apuntes, presentaciones y libros proporcionados por el docente para entender la base teórica de cada pregunta.',
    llm=llm_reporter,
    verbose=True,
    allow_delegation=False
)

agente_calificador = Agent(
    role='Docente Calificador Experto',
    goal=f'Evaluar las respuestas del estudiante comparándolas con el contexto de clase, aplicando una dificultad de /10.',
    backstory=f'Eres un profesor justo pero meticuloso. Evalúas exámenes basándote en un parámetro de dificultad. Actualmente la dificultad es . Si es 1, eres indulgente; si es 10, eres extremadamente riguroso.',
    llm=llm_grader,
    verbose=True,
    allow_delegation=False
)

agente_reportes = Agent(
    role='Administrador Académico',
    goal='Consolidar las evaluaciones y generar un informe final estructurado y claro.',
    backstory='Eres el encargado de comunicar los resultados. Tomas la calificación en crudo y redactas un informe profesional con puntuaciones, justificaciones de errores y conclusiones generales.',
    llm=llm_reporter,
    verbose=True,
    allow_delegation=False
)

def calificar_examen_ui(ruta_imagen, ruta_contexto, nivel_dificultad):
    tarea_extraccion = Task(
        description=f'Analiza la imagen en la ruta {ruta_imagen} y extrae todo el texto. Diferencia claramente cuáles son las preguntas y cuáles son las respuestas del estudiante.',
        expected_output='Un documento estructurado con preguntas y respuestas.',
        agent=agente_icr
    )

    tarea_contexto = Task(
        description=f'Revisa los temas abordados en el examen extraído y busca la teoría en el documento {ruta_contexto}.',
        expected_output='Resumen teórico de los temas del examen.',
        agent=agente_rag
    )

    tarea_calificacion = Task(
        description=f'Compara el examen con la teoría. Evalúa con dificultad {nivel_dificultad}/10. Asigna punteo y justifica errores.',
        expected_output='Análisis ítem por ítem con estado, punteo y justificación.',
        agent=agente_calificador
    )

    tarea_informe = Task(
        description='Redacta el informe final del examen. Incluye punteo total, individual, justificación de errores y conclusión general.',
        expected_output='Un informe formateado en Markdown.',
        agent=agente_reportes
    )

    crew_calificacion = Crew(
        agents=[agente_icr, agente_rag, agente_calificador, agente_reportes],
        tasks=[tarea_extraccion, tarea_contexto, tarea_calificacion, tarea_informe],
        process=Process.sequential,
        verbose=True
    )

    return crew_calificacion.kickoff()
