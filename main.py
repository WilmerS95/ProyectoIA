import os
import cv2
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from PIL import Image
import pytesseract
from pypdf import PdfReader

load_dotenv()

clave_nvidia = os.getenv("NVIDIA_API_KEY")
os.environ["OPENAI_API_KEY"] = clave_nvidia
os.environ["OPENAI_API_BASE"] = "https://integrate.api.nvidia.com/v1"

llm_vision = "openai/meta/llama-3.2-11b-vision-instruct"  
llm_grader = "openai/meta/llama-3.1-70b-instruct" 
llm_reporter = "openai/meta/llama-3.1-8b-instruct"


def extraer_texto_imagen(ruta):
    try:
        # Leer imagen con OpenCV
        img = cv2.imread(ruta)

        # Convertir a escala de grises
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Invertir colores (clave para fondo oscuro)
        inverted = cv2.bitwise_not(gray)

        # Aplicar umbral (binarizar)
        _, thresh = cv2.threshold(inverted, 150, 255, cv2.THRESH_BINARY)

        # Convertir a PIL
        pil_img = Image.fromarray(thresh)

        # OCR
        texto = pytesseract.image_to_string(
            pil_img,
            lang="spa",
            config='--psm 6'
        )

        return texto
    except Exception as e:
        print(e)
        return ""

def leer_pdf(ruta):
    try:
        reader = PdfReader(ruta)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text() or ""
        return texto
    except Exception as e:
        print(e)
        return ""


agente_icr = Agent(
    role='Especialista en ICR',
    goal='Extraer texto y estructurarlo en preguntas y respuestas.',
    backstory='Experto en OCR. Si no hay preguntas claras, debes indicarlo.',
    llm=llm_vision,
    verbose=True,
    allow_delegation=False
)

agente_rag = Agent(
    role='Investigador Académico',
    goal='Extraer teoría relevante del material.',
    backstory='Si el documento no contiene teoría útil, debes decirlo claramente.',
    llm=llm_reporter,
    verbose=True,
    allow_delegation=False
)

agente_calificador = Agent(
    role='Docente Calificador',
    goal='Evaluar respuestas con base en teoría.',
    backstory='Si no hay datos suficientes, responde "NO SE PUEDE EVALUAR". No inventes.',
    llm=llm_grader,
    verbose=True,
    allow_delegation=False
)

agente_reportes = Agent(
    role='Administrador Académico',
    goal='Generar informe final.',
    backstory='Si la evaluación no es válida, indícalo claramente.',
    llm=llm_reporter,
    verbose=True,
    allow_delegation=False
)

def calificar_examen_ui(ruta_imagen, ruta_contexto, nivel_dificultad):

    texto_imagen = extraer_texto_imagen(ruta_imagen)
    texto_pdf = leer_pdf(ruta_contexto)

    if not texto_imagen.strip():
        return "No se pudo extraer texto del examen."

    if not texto_pdf.strip():
        return "El PDF no contiene texto útil."


    tarea_extraccion = Task(
        description=f"""
        Este es el texto extraído del examen:

        {texto_imagen}

        Extrae preguntas y respuestas claramente.
        Si no hay preguntas, responde: NO HAY EXAMEN.
        """,
        expected_output='Preguntas y respuestas estructuradas.',
        agent=agente_icr
    )

    tarea_contexto = Task(
        description=f"""
        Este es el contenido del material de clase:

        {texto_pdf}

        Resume la teoría relevante para evaluar el examen.
        Si no aplica, responde: SIN CONTEXTO RELEVANTE.
        """,
        expected_output='Resumen teórico.',
        agent=agente_rag
    )

    tarea_calificacion = Task(
        description=f"""
        Eres un sistema de calificación automática.
        
        Debes evaluar TODAS las preguntas del examen usando la teoría proporcionada.
        
        Nivel de dificultad: {nivel_dificultad}/10
        
        ========================
        REGLAS OBLIGATORIAS
        ========================
        
        1. Identifica TODAS las preguntas detectadas.
        2. Determina el valor de cada pregunta:
           - Si el examen especifica puntos → respétalos exactamente.
           - Si NO especifica puntos:
                valor_por_pregunta = 100 / total_preguntas
        
        3. Clasifica cada respuesta SOLO como:
           - correcto
           - incorrecto
        
        4. Asignación de puntos:
           - correcto → obtiene el valor completo
           - incorrecto → 0 puntos
        
        5. NO puedes:
           - inventar preguntas
           - omitir preguntas
           - dar respuestas parciales
           - cambiar el formato
        
        6. Debes procesar TODAS las preguntas.
        
        ========================
        FORMATO OBLIGATORIO
        ========================
        
        RESULTADO:
        
        Pregunta 1:
        Respuesta: ...
        Estado: correcto/incorrecto
        Puntos: X
        Justificación: ...
        
        Pregunta 2:
        Respuesta: ...
        Estado: correcto/incorrecto
        Puntos: X
        Justificación: ...
        
        (repetir para TODAS las preguntas)
        
        ------------------------
        
        TOTAL:
        XX/100
        
        ========================
        
        Si no puedes evaluar:
        → responde EXACTAMENTE: NO SE PUEDE EVALUAR
        """,
        expected_output='Evaluación estructurada con puntaje por pregunta.',
        agent=agente_calificador
    )

    tarea_informe = Task(
        description="""
    Usa el resultado de la calificación anterior y genera un informe final.

    Debes incluir:

    - PUNTAJE TOTAL
    - RESUMEN GENERAL
    - ERRORES PRINCIPALES

    NO recalcules nada, solo resume.
    """,
        expected_output='Informe final estructurado.',
        agent=agente_reportes
    )

    crew = Crew(
        agents=[agente_icr, agente_rag, agente_calificador, agente_reportes],
        tasks=[tarea_extraccion, tarea_contexto, tarea_calificacion, tarea_informe],
        process=Process.sequential,
        verbose=True
    )

    resultado = crew.kickoff()

    return resultado.raw if hasattr(resultado, "raw") else str(resultado)