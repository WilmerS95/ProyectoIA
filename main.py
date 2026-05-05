import os
import uuid
import shutil
import tempfile
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader


# ============================================================
# CONFIGURACIÓN DE VARIABLES DE ENTORNO
# ============================================================

load_dotenv()

clave_nvidia = os.getenv("NVIDIA_API_KEY")
clave_gemini = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not clave_nvidia:
    raise ValueError("Falta NVIDIA_API_KEY en el archivo .env")

if not clave_gemini:
    raise ValueError("Falta GEMINI_API_KEY o GOOGLE_API_KEY en el archivo .env")

os.environ["OPENAI_API_KEY"] = clave_nvidia
os.environ["OPENAI_API_BASE"] = os.getenv(
    "OPENAI_API_BASE",
    "https://integrate.api.nvidia.com/v1"
)

os.environ["GEMINI_API_KEY"] = clave_gemini
os.environ["GOOGLE_API_KEY"] = clave_gemini


# ============================================================
# MODELOS
# ============================================================

# Gemini para lectura visual del examen.
llm_vision = "gemini/gemini-2.5-flash"

# NVIDIA para razonamiento/calificación.
llm_grader = "openai/meta/llama-3.1-70b-instruct"

# NVIDIA para redacción del informe final.
llm_reporter = "openai/meta/llama-3.1-8b-instruct"


# ============================================================
# LECTURA DE IMAGEN CON GEMINI
# ============================================================

def extraer_texto_imagen_gemini(ruta):
    """
    Extrae preguntas y respuestas desde una imagen usando Gemini.
    No requiere Tesseract instalado localmente.
    """
    try:
        cliente = genai.Client(api_key=clave_gemini)

        extension = Path(ruta).suffix.lower()

        if extension in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif extension == ".png":
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

        with open(ruta, "rb") as archivo:
            imagen_bytes = archivo.read()

        prompt = """
Eres un sistema experto en lectura de exámenes escritos.

Analiza cuidadosamente la imagen del examen y extrae el contenido de forma ordenada.

Tu tarea:
1. Identifica todas las preguntas visibles.
2. Identifica la respuesta escrita o seleccionada por el estudiante para cada pregunta.
3. Si hay opciones múltiples, identifica la opción marcada o seleccionada.
4. Si hay una respuesta escrita a mano, transcríbela lo mejor posible.
5. Si una parte no se entiende, escribe: "No legible".
6. No inventes preguntas.
7. No inventes respuestas.
8. Corrige únicamente errores evidentes de lectura, sin cambiar el sentido.
9. Si el examen tiene puntos por pregunta, conserva ese dato.

Devuelve únicamente este formato:

Pregunta 1:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en el examen: ... / No especificado

Pregunta 2:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en el examen: ... / No especificado

Si no puedes leer un examen válido, responde exactamente:
NO HAY EXAMEN LEGIBLE.
"""

        respuesta = cliente.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=imagen_bytes,
                    mime_type=mime_type
                ),
                prompt
            ]
        )

        return respuesta.text.strip() if respuesta.text else ""

    except Exception as e:
        print(f"Error usando Gemini para leer imagen: {e}")
        return ""


# Alias por compatibilidad con app.py anteriores.
def extraer_texto_imagen(ruta):
    return extraer_texto_imagen_gemini(ruta)


# ============================================================
# LECTURA DE ARCHIVOS DE CONTEXTO
# ============================================================

def leer_archivo_contexto(ruta):
    extension = Path(ruta).suffix.lower()

    try:
        if extension == ".pdf":
            reader = PdfReader(ruta)
            texto = ""

            for page_num, page in enumerate(reader.pages, start=1):
                contenido = page.extract_text() or ""
                if contenido.strip():
                    texto += f"\n\n[Página {page_num}]\n{contenido}"

            return texto.strip()

        if extension in [".txt", ".md"]:
            with open(ruta, "r", encoding="utf-8", errors="ignore") as archivo:
                return archivo.read().strip()

        if extension == ".docx":
            try:
                from docx import Document
            except ImportError:
                return (
                    "ERROR: Falta instalar python-docx para leer archivos DOCX."
                )

            doc = Document(ruta)
            texto = "\n".join([parrafo.text for parrafo in doc.paragraphs])
            return texto.strip()

        return f"Formato no soportado: {extension}"

    except Exception as e:
        print(f"Error leyendo archivo de contexto {ruta}: {e}")
        return ""


def leer_contextos(rutas_contexto):
    textos = []

    for index, ruta in enumerate(rutas_contexto, start=1):
        texto = leer_archivo_contexto(ruta)

        if texto.strip():
            textos.append(
                f"""
========================
DOCUMENTO DE CONTEXTO {index}
ARCHIVO: {Path(ruta).name}
========================
{texto}
"""
            )

    return "\n".join(textos).strip()


# ============================================================
# RAG PROFESIONAL CON CHROMADB
# ============================================================

def dividir_en_chunks(texto, tamano_chunk=1200, solapamiento=200):
    """
    Divide el texto en fragmentos con solapamiento.
    """
    texto = " ".join(texto.split())

    if not texto:
        return []

    chunks = []
    inicio = 0

    while inicio < len(texto):
        fin = inicio + tamano_chunk
        chunk = texto[inicio:fin].strip()

        if chunk:
            chunks.append(chunk)

        inicio += tamano_chunk - solapamiento

    return chunks


def construir_rag_temporal(texto_contexto):
    """
    Construye una base ChromaDB temporal para recuperar contexto relevante.
    """
    carpeta_temporal = tempfile.mkdtemp(prefix="rag_chroma_")

    try:
        embedding_function = SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        client = chromadb.PersistentClient(path=carpeta_temporal)

        collection = client.get_or_create_collection(
            name=f"contexto_examen_{uuid.uuid4().hex[:8]}",
            embedding_function=embedding_function
        )

        chunks = dividir_en_chunks(texto_contexto)

        if not chunks:
            return None, carpeta_temporal

        ids = [f"chunk_{i}" for i in range(len(chunks))]

        metadatas = [
            {"indice": i, "tipo": "material_clase"}
            for i in range(len(chunks))
        ]

        collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

        return collection, carpeta_temporal

    except Exception as e:
        print(f"Error construyendo RAG: {e}")

        if os.path.exists(carpeta_temporal):
            shutil.rmtree(carpeta_temporal, ignore_errors=True)

        return None, None


def recuperar_contexto_relevante(collection, consulta, n_resultados=8, limite_caracteres=14000):
    """
    Recupera fragmentos relevantes para una consulta.
    """
    if collection is None:
        return ""

    try:
        resultados = collection.query(
            query_texts=[consulta],
            n_results=n_resultados
        )

        documentos = resultados.get("documents", [[]])[0]

        contexto = []
        total = 0

        for doc in documentos:
            if not doc:
                continue

            if total + len(doc) > limite_caracteres:
                break

            contexto.append(doc)
            total += len(doc)

        return "\n\n--- FRAGMENTO RELEVANTE ---\n\n".join(contexto).strip()

    except Exception as e:
        print(f"Error recuperando contexto relevante: {e}")
        return ""


# ============================================================
# DIFICULTAD
# ============================================================

def obtener_criterio_dificultad(nivel_dificultad):
    if nivel_dificultad <= 3:
        return """
MODO FLEXIBLE:
- Acepta respuestas equivalentes aunque no usen las mismas palabras del material.
- Da crédito si el estudiante demuestra comprensión general.
- Penaliza solo errores conceptuales claros.
- No seas estricto con ortografía, redacción o falta de detalle menor.
- Puedes otorgar puntuación alta si la idea principal es correcta.
"""

    if nivel_dificultad <= 7:
        return """
MODO ESTÁNDAR:
- Exige conceptos correctos y relación clara con el material.
- Acepta redacción diferente si el concepto central es correcto.
- Penaliza respuestas incompletas, ambiguas o demasiado generales.
- Otorga puntuación media si la respuesta tiene parte del concepto pero le falta precisión.
"""

    return """
MODO ESTRICTO:
- Exige precisión conceptual, claridad, completitud y relación directa con el material.
- Penaliza omisiones importantes.
- No aceptes respuestas vagas aunque se parezcan al tema.
- Otorga puntuación baja si la respuesta no explica el concepto con suficiente profundidad.
"""


# ============================================================
# AGENTES
# ============================================================

agente_icr = Agent(
    role="Especialista en ICR",
    goal="Extraer y estructurar preguntas y respuestas de exámenes escritos.",
    backstory=(
        "Eres experto en interpretación de exámenes escaneados o fotografiados. "
        "Tu tarea es ordenar preguntas y respuestas sin inventar información."
    ),
    llm=llm_vision,
    verbose=True,
    allow_delegation=False
)

agente_calificador = Agent(
    role="Docente Calificador Profesional",
    goal="Evaluar respuestas de estudiantes con base en una rúbrica y contexto académico.",
    backstory=(
        "Eres un docente calificador justo, preciso y profesional. "
        "Evalúas con base en el material proporcionado, no inventas datos, "
        "explicas el motivo de cada puntuación y das retroalimentación útil."
    ),
    llm=llm_grader,
    verbose=True,
    allow_delegation=False
)

agente_reportes = Agent(
    role="Administrador Académico",
    goal="Generar un informe final claro y ordenado.",
    backstory=(
        "Eres experto en presentar resultados académicos de forma clara, "
        "ordenada y entendible para docentes y estudiantes."
    ),
    llm=llm_reporter,
    verbose=True,
    allow_delegation=False
)


# ============================================================
# FUNCIÓN PRINCIPAL PARA STREAMLIT
# ============================================================

def calificar_examen_ui(ruta_imagen, rutas_contexto, nivel_dificultad):
    carpeta_rag = None

    try:
        texto_examen = extraer_texto_imagen_gemini(ruta_imagen)

        if not texto_examen.strip():
            return "No se pudo extraer texto del examen usando Gemini."

        if "NO HAY EXAMEN LEGIBLE" in texto_examen.upper():
            return "No se pudo leer un examen válido en la imagen."

        texto_contexto_completo = leer_contextos(rutas_contexto)

        if not texto_contexto_completo.strip():
            return "Los archivos de contexto no contienen texto útil."

        criterio_dificultad = obtener_criterio_dificultad(nivel_dificultad)

        collection, carpeta_rag = construir_rag_temporal(texto_contexto_completo)

        if collection is None:
            return "No se pudo construir la base RAG con los materiales proporcionados."

        contexto_relevante = recuperar_contexto_relevante(
            collection=collection,
            consulta=texto_examen,
            n_resultados=10,
            limite_caracteres=16000
        )

        if not contexto_relevante.strip():
            return "No se encontraron fragmentos relevantes en el material para evaluar el examen."

        tarea_extraccion = Task(
            description=f"""
Eres un especialista en lectura de exámenes escritos.

Gemini extrajo este contenido desde la imagen del examen:

{texto_examen}

Tu tarea:
1. Revisa y estructura las preguntas y respuestas.
2. No inventes preguntas.
3. No inventes respuestas.
4. Si una respuesta no aparece o no se entiende, escribe: "No legible".
5. Conserva los puntos indicados si aparecen.

FORMATO OBLIGATORIO:

Pregunta 1:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en el examen: ... / No especificado

Pregunta 2:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en el examen: ... / No especificado

Si no hay examen válido, responde exactamente:
NO HAY EXAMEN.
""",
            expected_output="Preguntas y respuestas del estudiante claramente estructuradas.",
            agent=agente_icr
        )

        tarea_calificacion = Task(
            description=f"""
Eres un DOCENTE CALIFICADOR PROFESIONAL.

Debes calificar el examen usando únicamente:

1. Las preguntas y respuestas extraídas del examen.
2. Los fragmentos relevantes recuperados por RAG desde el material del profesor.
3. El nivel de dificultad seleccionado.

========================
EXAMEN EXTRAÍDO
========================

{texto_examen}

========================
CONTEXTO RELEVANTE RAG
========================

{contexto_relevante}

========================
NIVEL DE DIFICULTAD
========================

Nivel seleccionado: {nivel_dificultad}/10

{criterio_dificultad}

========================
REGLAS DE CALIFICACIÓN
========================

1. Evalúa TODAS las preguntas detectadas.
2. No inventes preguntas ni respuestas.
3. Si una respuesta está como "No legible", califícala con 0.
4. Si el examen trae puntos por pregunta, respeta esos puntos.
5. Si el examen NO trae puntos:
   - asigna 10 puntos por pregunta;
   - al final convierte el total a escala de 100.
6. Puedes dar puntuación parcial si la respuesta tiene parte del concepto correcto.
7. El nivel de dificultad debe afectar la puntuación:
   - flexible: más tolerante;
   - estándar: equilibrio;
   - estricto: más exigente.
8. Usa el contexto RAG como base para la respuesta esperada.
9. No califiques con base en conocimientos externos si el material no lo respalda.
10. La justificación debe explicar exactamente por qué se dio esa puntuación.
11. La retroalimentación debe decir cómo mejorar la respuesta.

========================
FORMATO OBLIGATORIO
========================

# Informe de Calificación

## Pregunta 1
**Pregunta:** ...
**Respuesta del estudiante:** ...
**Respuesta esperada según el material:** ...
**Puntuación obtenida:** X/Y
**Justificación de la puntuación:** ...
**Retroalimentación para el estudiante:** ...
**Tema relacionado del material:** ...

## Pregunta 2
**Pregunta:** ...
**Respuesta del estudiante:** ...
**Respuesta esperada según el material:** ...
**Puntuación obtenida:** X/Y
**Justificación de la puntuación:** ...
**Retroalimentación para el estudiante:** ...
**Tema relacionado del material:** ...

Repite el mismo formato para TODAS las preguntas.

## Resumen de Punteo
**Punteo obtenido:** X
**Punteo máximo:** Y
**Nota final en escala de 100:** XX/100

## Conclusión General
Explica el desempeño general del estudiante.

## Recomendaciones de Estudio
Da recomendaciones concretas con base en los errores detectados.

Si no puedes evaluar por falta de información, responde exactamente:
NO SE PUEDE EVALUAR CON EL MATERIAL PROPORCIONADO.
""",
            expected_output=(
                "Informe profesional de calificación por pregunta, con respuesta esperada, "
                "puntuación, justificación y retroalimentación."
            ),
            agent=agente_calificador
        )

        tarea_informe = Task(
            description="""
Toma la calificación anterior y mejora únicamente la presentación final.

Reglas:
1. No cambies puntuaciones.
2. No recalcules notas.
3. No inventes nuevas preguntas.
4. No elimines justificaciones.
5. Mantén el formato por pregunta.
6. Haz que el informe sea claro para docente y estudiante.

El informe final debe conservar:

# Informe de Calificación

## Pregunta N
**Pregunta**
**Respuesta del estudiante**
**Respuesta esperada según el material**
**Puntuación obtenida**
**Justificación de la puntuación**
**Retroalimentación para el estudiante**
**Tema relacionado del material**

## Resumen de Punteo
## Conclusión General
## Recomendaciones de Estudio
""",
            expected_output="Informe final profesional y ordenado en Markdown.",
            agent=agente_reportes
        )

        crew = Crew(
            agents=[agente_icr, agente_calificador, agente_reportes],
            tasks=[tarea_extraccion, tarea_calificacion, tarea_informe],
            process=Process.sequential,
            verbose=True
        )

        resultado = crew.kickoff()

        return resultado.raw if hasattr(resultado, "raw") else str(resultado)

    finally:
        if carpeta_rag and os.path.exists(carpeta_rag):
            shutil.rmtree(carpeta_rag, ignore_errors=True)