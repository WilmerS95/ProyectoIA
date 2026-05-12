import os
import re
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader


load_dotenv()

clave_nvidia = os.getenv("NVIDIA_API_KEY")
clave_gemini = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not clave_nvidia:
    raise ValueError("Falta NVIDIA_API_KEY en el .env")

if not clave_gemini:
    raise ValueError("Falta GEMINI_API_KEY o GOOGLE_API_KEY en el .env")

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

llm_grader = "openai/meta/llama-3.1-70b-instruct"


# ============================================================
# MODELO DE DATOS
# ============================================================

@dataclass
class PreguntaExamen:
    id_global: int
    serie: str
    numero_local: int | None
    bloque: str
    valor: float


# ============================================================
# GEMINI: LECTURA DE IMAGEN / ICR
# ============================================================

def extraer_texto_imagen_gemini(ruta):
    try:
        cliente = genai.Client(api_key=clave_gemini)

        extension = Path(ruta).suffix.lower()
        mime_type = "image/png" if extension == ".png" else "image/jpeg"

        with open(ruta, "rb") as archivo:
            imagen_bytes = archivo.read()

        prompt = """
Eres un sistema experto en ICR para exámenes escritos, impresos o manuscritos.

Analiza TODA la imagen:
- Encabezado.
- Tabla de puntuación.
- Instrucciones.
- Series.
- Preguntas.
- Respuestas del estudiante.

REGLAS IMPORTANTES:
1. Si existe una tabla de "Escala de puntuación y valoración", esa tabla tiene prioridad.
2. Si arriba dice algo como "15/100", pero la tabla dice Serie 1, Serie 2 y Total, usa la tabla.
3. No confundas "Valor 10 puntos" del título con la tabla si la tabla contradice ese dato.
4. Extrae los valores reales de la tabla si aparecen.
5. No inventes preguntas.
6. No inventes respuestas.
7. Ignora marcas de corrección si existen.
8. Conserva el orden real del examen.
9. Si algo no se entiende, escribe "No legible".

Devuelve exactamente este formato:

RUBRICA_DETECTADA:
Serie 1: ... / No especificado
Serie 2: ... / No especificado
Total: ... / No especificado
Fuente de puntuación: tabla / instrucciones / encabezado / no especificado

PREGUNTAS_EXTRAIDAS:

Serie: Primera serie
Pregunta 1:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en la pregunta: ... / No especificado

Pregunta 2:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en la pregunta: ... / No especificado

Serie: Segunda serie
Pregunta 1:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en la pregunta: ... / No especificado

Si no puedes leer el examen, responde:
NO HAY EXAMEN LEGIBLE.
"""

        modelos_gemini = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ]

        ultimo_error = None

        for modelo in modelos_gemini:
            for intento in range(2):
                try:
                    respuesta = cliente.models.generate_content(
                        model=modelo,
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
                    ultimo_error = e
                    print(f"Error usando {modelo}, intento {intento + 1}/2: {e}")
                    time.sleep(2)

        print(f"No se pudo leer imagen. Último error: {ultimo_error}")
        return ""

    except Exception as e:
        print(f"Error usando Gemini para leer imagen: {e}")
        return ""


def extraer_texto_imagen(ruta):
    return extraer_texto_imagen_gemini(ruta)


# ============================================================
# LECTURA DE ARCHIVOS DE REFERENCIA
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
                return "ERROR: Falta instalar python-docx para leer DOCX."

            doc = Document(ruta)
            return "\n".join([p.text for p in doc.paragraphs]).strip()

        return ""

    except Exception as e:
        print(f"Error leyendo contexto {ruta}: {e}")
        return ""


def leer_contextos(rutas_contexto):
    textos = []

    for i, ruta in enumerate(rutas_contexto, start=1):
        texto = leer_archivo_contexto(ruta)

        if texto.strip():
            textos.append(
                f"""
========================
DOCUMENTO {i}
ARCHIVO: {Path(ruta).name}
========================
{texto}
"""
            )

    return "\n".join(textos).strip()


# ============================================================
# UTILIDADES
# ============================================================

def normalizar_numero(valor):
    if valor is None:
        return None

    valor = str(valor).strip().replace(",", ".")

    try:
        return float(valor)
    except Exception:
        return None


def buscar_numero_patron(texto, patrones):
    for patron in patrones:
        match = re.search(patron, texto, flags=re.IGNORECASE)
        if match:
            numero = normalizar_numero(match.group(1))
            if numero is not None:
                return numero

    return None


def detectar_rubrica(texto_examen, cantidad_preguntas):
    """
    Detecta puntuación del examen.

    Prioridad:
    1. Tabla o bloque RUBRICA_DETECTADA.
    2. Serie 1 + Serie 2 + Total.
    3. Total general.
    4. Si no detecta nada: 100 puntos.
    """

    texto = texto_examen.replace("\n", " ")

    serie1 = buscar_numero_patron(
        texto,
        [
            r"Serie\s*1\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
            r"Primera\s+serie\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
            r"Serie\s*1\s+([0-9]+(?:[.,][0-9]+)?)",
        ]
    )

    serie2 = buscar_numero_patron(
        texto,
        [
            r"Serie\s*2\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
            r"Segunda\s+serie\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
            r"Serie\s*2\s+([0-9]+(?:[.,][0-9]+)?)",
        ]
    )

    total = buscar_numero_patron(
        texto,
        [
            r"Total\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
            r"Total\s+([0-9]+(?:[.,][0-9]+)?)",
            r"valor\s+total\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",
        ]
    )

    # Caso específico frecuente: la imagen puede decir 15/100 arriba,
    # pero la tabla real dice Serie 1, Serie 2 y Total.
    if serie1 is not None or serie2 is not None:
        serie1 = serie1 if serie1 is not None else 0
        serie2 = serie2 if serie2 is not None else 0
        total_series = serie1 + serie2

        if total is None or abs(total - total_series) <= 1:
            total = total_series

        return {
            "serie1": serie1,
            "serie2": serie2,
            "total": total if total else total_series,
            "fuente": "rubrica detectada en examen"
        }

    if total is not None and total > 0 and total <= 100:
        return {
            "serie1": None,
            "serie2": None,
            "total": total,
            "fuente": "total general detectado"
        }

    return {
        "serie1": None,
        "serie2": None,
        "total": 100.0,
        "fuente": "no se detectó puntuación; se asignó escala de 100"
    }


def hash_archivos(rutas):
    h = hashlib.sha256()

    for ruta in rutas:
        with open(ruta, "rb") as f:
            h.update(f.read())

    return h.hexdigest()[:24]


def dividir_en_chunks(texto, tamano_chunk=850, solapamiento=120):
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


def detectar_serie(linea):
    linea_lower = linea.lower()

    if (
        "primera serie" in linea_lower
        or "serie: primera" in linea_lower
        or "serie 1" in linea_lower
    ):
        return "Serie 1"

    if (
        "segunda serie" in linea_lower
        or "serie: segunda" in linea_lower
        or "serie 2" in linea_lower
    ):
        return "Serie 2"

    return None


def dividir_preguntas_con_series(texto_examen):
    lineas = texto_examen.splitlines()

    preguntas = []
    serie_actual = "Sin serie"
    bloque_actual = []
    numero_actual = None

    for linea in lineas:
        serie_detectada = detectar_serie(linea)

        if serie_detectada:
            serie_actual = serie_detectada
            continue

        match_pregunta = re.match(
            r"\s*Pregunta\s+(\d+)\s*:",
            linea,
            flags=re.IGNORECASE
        )

        if match_pregunta:
            if bloque_actual:
                preguntas.append(
                    {
                        "serie": serie_actual,
                        "numero_local": numero_actual,
                        "bloque": "\n".join(bloque_actual).strip()
                    }
                )

            numero_actual = int(match_pregunta.group(1))
            bloque_actual = [linea]

        else:
            if bloque_actual:
                bloque_actual.append(linea)

    if bloque_actual:
        preguntas.append(
            {
                "serie": serie_actual,
                "numero_local": numero_actual,
                "bloque": "\n".join(bloque_actual).strip()
            }
        )

    if not preguntas:
        return [
            {
                "serie": "Sin serie",
                "numero_local": 1,
                "bloque": texto_examen
            }
        ]

    return preguntas


def asignar_puntajes(preguntas_raw, rubrica):
    total = float(rubrica["total"])

    serie1_count = sum(1 for p in preguntas_raw if p["serie"] == "Serie 1")
    serie2_count = sum(1 for p in preguntas_raw if p["serie"] == "Serie 2")

    preguntas = []

    for idx, p in enumerate(preguntas_raw, start=1):
        serie = p["serie"]

        if rubrica["serie1"] is not None or rubrica["serie2"] is not None:
            if serie == "Serie 1" and serie1_count > 0:
                valor = float(rubrica["serie1"]) / serie1_count

            elif serie == "Serie 2" and serie2_count > 0:
                valor = float(rubrica["serie2"]) / serie2_count

            else:
                valor = total / max(len(preguntas_raw), 1)

        else:
            valor = total / max(len(preguntas_raw), 1)

        preguntas.append(
            PreguntaExamen(
                id_global=idx,
                serie=serie,
                numero_local=p["numero_local"],
                bloque=p["bloque"],
                valor=round(valor, 2)
            )
        )

    return preguntas


def construir_tabla_rubrica(preguntas, rubrica):
    filas = []

    for p in preguntas:
        filas.append(
            f"Pregunta global {p.id_global} | {p.serie} | Pregunta {p.numero_local}: valor máximo {p.valor} puntos"
        )

    return f"""
Fuente de puntuación: {rubrica["fuente"]}
Serie 1: {rubrica["serie1"] if rubrica["serie1"] is not None else "No especificado"}
Serie 2: {rubrica["serie2"] if rubrica["serie2"] is not None else "No especificado"}
Total del examen: {rubrica["total"]}

Distribución por pregunta:
{chr(10).join(filas)}
"""


# ============================================================
# RAG CON CACHE
# ============================================================

def construir_rag_cache(rutas_contexto, texto_contexto):
    cache_id = hash_archivos(rutas_contexto)

    base_dir = Path(".rag_cache")
    base_dir.mkdir(exist_ok=True)

    carpeta_cache = base_dir / cache_id
    carpeta_cache.mkdir(exist_ok=True)

    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    client = chromadb.PersistentClient(path=str(carpeta_cache))

    collection = client.get_or_create_collection(
        name=f"contexto_{cache_id}",
        embedding_function=embedding_function
    )

    try:
        cantidad = collection.count()
    except Exception:
        cantidad = 0

    if cantidad == 0:
        chunks = dividir_en_chunks(texto_contexto)

        if not chunks:
            return None

        ids = [f"chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"indice": i} for i in range(len(chunks))]

        collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

    return collection


def consulta_pregunta(pregunta):
    return re.sub(r"\s+", " ", pregunta.bloque).strip()[:600]


def recuperar_contexto_pregunta(collection, pregunta, n_resultados=3, limite_caracteres=3800):
    if collection is None:
        return ""

    try:
        cantidad = collection.count()
        n = min(n_resultados, cantidad)

        resultados = collection.query(
            query_texts=[consulta_pregunta(pregunta)],
            n_results=n
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
        print(f"Error recuperando contexto por pregunta: {e}")
        return ""


def construir_contexto_por_pregunta(collection, preguntas):
    secciones = []

    for p in preguntas:
        contexto = recuperar_contexto_pregunta(collection, p)

        if not contexto.strip():
            contexto = "No se encontró contexto suficiente para esta pregunta."

        secciones.append(
            f"""
========================
PREGUNTA GLOBAL {p.id_global}
{p.serie} - Pregunta {p.numero_local}
VALOR MÁXIMO: {p.valor} puntos
========================

PREGUNTA Y RESPUESTA:
{p.bloque}

CONTEXTO RELEVANTE DEL MATERIAL:
{contexto}
"""
        )

    return "\n".join(secciones).strip()


# ============================================================
# DIFICULTAD 1 A 10
# ============================================================

def obtener_criterio_dificultad(nivel):
    return f"""
Nivel seleccionado: {nivel}/10

ESCALA:
1 = Modo amigo extremo.
2 = Muy indulgente.
3 = Flexible.
4 = Moderadamente flexible.
5 = Estándar.
6 = Estándar exigente.
7 = Estricto.
8 = Muy estricto.
9 = Experto.
10 = Experto riguroso.

REGLAS:
- Nivel 1-2: si la idea principal está, casi todo el puntaje.
- Nivel 3-4: acepta respuestas breves si el concepto central es correcto.
- Nivel 5: equilibrio; no castigues demasiado detalles secundarios.
- Nivel 6: exige concepto correcto y algo de precisión.
- Nivel 7: exige precisión, pero permite parciales justos.
- Nivel 8: penaliza omisiones importantes.
- Nivel 9-10: exige definición técnica, precisión y completitud.

RANGOS PARA RESPUESTAS PARCIALES:
- Nivel 1-2: parcial = 70% a 95%.
- Nivel 3-4: parcial = 60% a 90%.
- Nivel 5-6: parcial = 50% a 85%.
- Nivel 7-8: parcial = 35% a 75%.
- Nivel 9-10: parcial = 20% a 60%.

IMPORTANTE:
No califiques nivel {nivel} como si fuera nivel 10.
La dificultad debe afectar el puntaje, pero siempre con justicia académica.
"""


# ============================================================
# AGENTE CALIFICADOR
# ============================================================

agente_calificador = Agent(
    role="Docente Calificador Profesional",
    goal="Calificar exámenes con precisión usando rúbrica, contexto y criterio académico.",
    backstory=(
        "Eres un docente universitario justo, claro y profesional. "
        "Calificas con base en el material del profesor, aplicas la rúbrica real "
        "y explicas cada puntuación de forma entendible."
    ),
    llm=llm_grader,
    verbose=True,
    allow_delegation=False
)


# ============================================================
# FUNCIÓN PRINCIPAL PARA STREAMLIT
# ============================================================

def calificar_examen_ui(ruta_imagen, rutas_contexto, nivel_dificultad):
    texto_examen = extraer_texto_imagen_gemini(ruta_imagen)

    if not texto_examen.strip():
        return "No se pudo extraer texto del examen usando Gemini."

    if "NO HAY EXAMEN LEGIBLE" in texto_examen.upper():
        return "No se pudo leer un examen válido en la imagen."

    texto_contexto = leer_contextos(rutas_contexto)

    if not texto_contexto.strip():
        return "Los archivos de contexto no contienen texto útil."

    preguntas_raw = dividir_preguntas_con_series(texto_examen)
    rubrica = detectar_rubrica(texto_examen, len(preguntas_raw))
    preguntas = asignar_puntajes(preguntas_raw, rubrica)
    tabla_rubrica = construir_tabla_rubrica(preguntas, rubrica)

    collection = construir_rag_cache(rutas_contexto, texto_contexto)

    if collection is None:
        return "No se pudo construir o cargar el RAG del material."

    contexto_por_pregunta = construir_contexto_por_pregunta(collection, preguntas)
    criterio = obtener_criterio_dificultad(nivel_dificultad)

    tarea = Task(
        description=f"""
Eres un DOCENTE CALIFICADOR PROFESIONAL.

Debes calificar usando:
1. El texto extraído del examen.
2. El contexto relevante recuperado por RAG para cada pregunta.
3. La rúbrica calculada por el sistema.
4. El nivel de dificultad seleccionado.

========================
EXAMEN EXTRAÍDO
========================

{texto_examen}

========================
RÚBRICA CALCULADA POR EL SISTEMA
========================

{tabla_rubrica}

REGLAS DE PUNTUACIÓN:
- Usa exactamente la rúbrica calculada por el sistema.
- No cambies el total del examen.
- No califiques sobre 150.
- No asignes 10 puntos por pregunta salvo que la rúbrica lo indique.
- Si no se detectó puntuación, el sistema ya asignó escala de 100.
- Distingue preguntas globales aunque la segunda serie vuelva a empezar desde 1.
- Al final convierte a escala de 100.

========================
CONTEXTO POR PREGUNTA
========================

{contexto_por_pregunta}

========================
DIFICULTAD
========================

{criterio}

========================
CRITERIOS DE CALIFICACIÓN
========================

Para cada pregunta:
- Correcta: puntaje completo o casi completo.
- Parcial: usa el rango permitido según dificultad.
- Incorrecta: 0 puntos o mínimo simbólico solo si tiene relación.
- Si dice "No legible": 0 puntos.
- Si el contexto no alcanza, dilo claramente.

No inventes información.
No cambies las respuestas del estudiante.
No uses conocimiento externo si contradice el material.
Sé específico.
Evita justificaciones genéricas.

========================
FORMATO FINAL OBLIGATORIO EN MARKDOWN
========================

# Informe de Calificación

## Resumen General

**Punteo obtenido:** X/{rubrica["total"]}

**Nota final en escala de 100:** XX/100

**Nivel de dificultad aplicado:** {nivel_dificultad}/10

**Fuente de puntuación:** {rubrica["fuente"]}

## Detalle por Pregunta

### Pregunta global 1

**Serie:** ...

**Pregunta:** ...

**Respuesta del estudiante:** ...

**Respuesta esperada según el material:** ...

**Valor máximo:** ... puntos

**Puntuación obtenida:** ... puntos

**Estado:** Correcta / Parcial / Incorrecta

**Justificación:** ...

**Retroalimentación:** ...

Repite el mismo formato para todas las preguntas globales.

## Clasificación Final

**Buenas:** ...

**Parciales:** ...

**Incorrectas:** ...

## Conclusión General

...

## Recomendaciones de Estudio

...
""",
        expected_output="Informe profesional en Markdown con nota real, dificultad aplicada y escala de 100.",
        agent=agente_calificador
    )

    crew = Crew(
        agents=[agente_calificador],
        tasks=[tarea],
        process=Process.sequential,
        verbose=True
    )

    resultado = crew.kickoff()

    return resultado.raw if hasattr(resultado, "raw") else str(resultado)