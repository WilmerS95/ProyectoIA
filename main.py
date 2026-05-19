import os
import re
import json
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Falta GEMINI_API_KEY o GOOGLE_API_KEY en el archivo .env")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

MODELO_PRINCIPAL = "gemini-2.5-flash"
MODELO_FALLBACK = "gemini-2.5-flash-lite"


# ============================================================
# CARPETAS CACHE
# ============================================================

CACHE_DIR = Path(".cache_examenes")
CACHE_DIR.mkdir(exist_ok=True)

RAG_DIR = Path(".rag_cache")
RAG_DIR.mkdir(exist_ok=True)


# ============================================================
# DATOS
# ============================================================

@dataclass
class PreguntaExamen:
    id_global: int
    serie: str
    numero_local: Optional[int]
    bloque: str
    valor: float


# ============================================================
# UTILIDADES CACHE
# ============================================================

def hash_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def hash_archivos(rutas):
    h = hashlib.sha256()
    for ruta in rutas:
        with open(ruta, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def cargar_json_cache(nombre):
    ruta = CACHE_DIR / nombre
    if not ruta.exists():
        return None
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def guardar_json_cache(nombre, data):
    ruta = CACHE_DIR / nombre
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"No se pudo guardar cache {nombre}: {e}")


# ============================================================
# GEMINI DIRECTO
# ============================================================

def llamar_gemini(prompt: str, imagen_bytes: bytes = None, mime_type: str = None) -> str:
    cliente = genai.Client(api_key=GEMINI_API_KEY)

    for modelo in [MODELO_PRINCIPAL, MODELO_FALLBACK]:
        for intento in range(2):
            try:
                if imagen_bytes and mime_type:
                    contents = [
                        types.Part.from_bytes(
                            data=imagen_bytes,
                            mime_type=mime_type
                        ),
                        prompt,
                    ]
                else:
                    contents = [prompt]

                respuesta = cliente.models.generate_content(
                    model=modelo,
                    contents=contents,
                )

                texto = respuesta.text.strip() if respuesta.text else ""
                if texto:
                    return texto

            except Exception as e:
                print(f"[Gemini] {modelo} intento {intento + 1}/2 falló: {e}")
                time.sleep(1)

    return ""


# ============================================================
# OCR / ICR
# ============================================================

OCR_PROMPT = """
Eres un sistema experto en OCR e ICR para exámenes académicos.

Debes leer TODA la imagen:
- encabezado
- instrucciones
- tabla de puntuación
- series
- preguntas
- respuestas del estudiante
- valores de cada serie
- valores de cada pregunta

REGLAS IMPORTANTES:
1. No inventes preguntas.
2. No inventes respuestas.
3. Si hay tabla de puntuación, úsala como fuente principal.
4. Si arriba dice algo como 15/100 pero la tabla indica Serie 1, Serie 2 y Total, usa la tabla.
5. Conserva el orden real del examen.
6. Si algo no se entiende, escribe "No legible".
7. Extrae preguntas y respuestas de forma clara.
8. Si una pregunta dice "(1 punto)", "(2 puntos)", etc., extrae ese valor.
9. No confundas escala de calificación con valor real del examen.
10. No ignores textos pequeños donde diga "Valor 10 puntos", "Valor 5 puntos", "1 punto", etc.

OBLIGATORIO PARA PUNTEO:
- Si ves "PRIMERA SERIE: Valor 10 puntos", escribe exactamente:
Serie 1: 10
- Si ves "SEGUNDA SERIE: Valor 5 puntos", escribe exactamente:
Serie 2: 5
- Si ves "Total 15", escribe exactamente:
Total: 15
- Si una pregunta dice "(1 punto)", escribe:
Puntos indicados en la pregunta: 1
- Nunca ignores los valores aunque estén pequeños o al lado del título.

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

Serie: Segunda serie
Pregunta 1:
Pregunta: ...
Respuesta del estudiante: ...
Puntos indicados en la pregunta: ... / No especificado

Si no puedes leer el examen, responde:
NO HAY EXAMEN LEGIBLE.
"""


def extraer_texto_imagen_gemini(ruta_imagen: str) -> str:
    imagen_hash = hash_archivo(ruta_imagen)
    cache_name = f"ocr_{imagen_hash}.json"

    cache = cargar_json_cache(cache_name)
    if cache and cache.get("texto"):
        print("✅ OCR desde cache.")
        return cache["texto"]

    extension = Path(ruta_imagen).suffix.lower()
    mime_type = "image/png" if extension == ".png" else "image/jpeg"

    with open(ruta_imagen, "rb") as f:
        imagen_bytes = f.read()

    texto = llamar_gemini(
        OCR_PROMPT,
        imagen_bytes=imagen_bytes,
        mime_type=mime_type
    )

    if texto:
        guardar_json_cache(cache_name, {"texto": texto})

    return texto


def extraer_texto_imagen(ruta_imagen: str) -> str:
    return extraer_texto_imagen_gemini(ruta_imagen)


# ============================================================
# LECTURA DE DOCUMENTOS
# ============================================================

def leer_archivo_contexto(ruta: str) -> str:
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
            with open(ruta, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()

        if extension == ".docx":
            from docx import Document
            doc = Document(ruta)
            return "\n".join([p.text for p in doc.paragraphs]).strip()

        return ""

    except Exception as e:
        print(f"Error leyendo contexto {ruta}: {e}")
        return ""


def leer_contextos(rutas_contexto: list) -> str:
    contexto_hash = hash_archivos(rutas_contexto)
    cache_name = f"contexto_{contexto_hash}.json"

    cache = cargar_json_cache(cache_name)
    if cache and cache.get("texto"):
        print("✅ Contexto desde cache.")
        return cache["texto"]

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

    texto_final = "\n".join(textos).strip()

    if texto_final:
        guardar_json_cache(cache_name, {"texto": texto_final})

    return texto_final


# ============================================================
# RÚBRICA Y PUNTEO
# ============================================================

def normalizar_numero(valor):
    if valor is None:
        return None

    try:
        return float(str(valor).strip().replace(",", "."))
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


def contar_preguntas_ocr(texto_examen: str) -> int:
    return len(re.findall(r"Pregunta\s+\d+\s*:", texto_examen, flags=re.IGNORECASE))


def detectar_rubrica(texto_examen: str) -> dict:
    texto = texto_examen.replace("\n", " ")

    serie1 = buscar_numero_patron(texto, [
        r"Serie\s*1\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Primera\s+serie\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Primera\s+serie.*?Valor\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",
        r"PRIMERA\s+SERIE\s*:\s*Valor\s*([0-9]+(?:[.,][0-9]+)?)",
    ])

    serie2 = buscar_numero_patron(texto, [
        r"Serie\s*2\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Segunda\s+serie\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Segunda\s+serie.*?Valor\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",
        r"SEGUNDA\s+SERIE\s*:\s*Valor\s*([0-9]+(?:[.,][0-9]+)?)",
    ])

    total = buscar_numero_patron(texto, [
        r"Total\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Total\s+([0-9]+(?:[.,][0-9]+)?)",
        r"valor\s+total\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",
        r"Punteo\s+total\s*[:=]?\s*([0-9]+(?:[.,][0-9]+)?)",
    ])

    if serie1 is not None or serie2 is not None:
        serie1 = serie1 if serie1 is not None else 0
        serie2 = serie2 if serie2 is not None else 0
        total_series = serie1 + serie2

        if total is None or abs(total - total_series) <= 1:
            total = total_series

        return {
            "serie1": serie1,
            "serie2": serie2,
            "total": total or total_series,
            "fuente": "rúbrica detectada en examen"
        }

    if total is not None and 0 < total <= 100:
        return {
            "serie1": None,
            "serie2": None,
            "total": total,
            "fuente": "total general detectado"
        }

    cantidad_preguntas = contar_preguntas_ocr(texto_examen)

    if cantidad_preguntas > 0:
        return {
            "serie1": None,
            "serie2": None,
            "total": float(cantidad_preguntas),
            "fuente": f"no se detectó tabla de puntuación; se asumió 1 punto por cada una de las {cantidad_preguntas} preguntas"
        }

    return {
        "serie1": None,
        "serie2": None,
        "total": 100.0,
        "fuente": "no se detectó puntuación; se asignó escala de 100"
    }


# ============================================================
# PREGUNTAS
# ============================================================

def detectar_serie(linea: str):
    l = linea.lower()

    if "primera serie" in l or "serie: primera" in l or "serie 1" in l:
        return "Serie 1"

    if "segunda serie" in l or "serie: segunda" in l or "serie 2" in l:
        return "Serie 2"

    return None


def dividir_preguntas_con_series(texto_examen: str) -> list:
    lineas = texto_examen.splitlines()
    preguntas = []
    serie_actual = "Sin serie"
    bloque_actual = []
    numero_actual = None

    for linea in lineas:
        serie_detectada = detectar_serie(linea)

        if serie_detectada:
            if bloque_actual:
                preguntas.append({
                    "serie": serie_actual,
                    "numero_local": numero_actual,
                    "bloque": "\n".join(bloque_actual).strip()
                })
                bloque_actual = []
                numero_actual = None

            serie_actual = serie_detectada
            continue

        match_pregunta = re.match(
            r"\s*Pregunta\s+(\d+)\s*:",
            linea,
            flags=re.IGNORECASE
        )

        if match_pregunta:
            if bloque_actual:
                preguntas.append({
                    "serie": serie_actual,
                    "numero_local": numero_actual,
                    "bloque": "\n".join(bloque_actual).strip()
                })

            numero_actual = int(match_pregunta.group(1))
            bloque_actual = [linea]
        else:
            if bloque_actual:
                bloque_actual.append(linea)

    if bloque_actual:
        preguntas.append({
            "serie": serie_actual,
            "numero_local": numero_actual,
            "bloque": "\n".join(bloque_actual).strip()
        })

    preguntas_limpias = [
        p for p in preguntas
        if "Pregunta:" in p["bloque"] and "Respuesta del estudiante:" in p["bloque"]
    ]

    if not preguntas_limpias and texto_examen.strip():
        return [{
            "serie": "Sin serie",
            "numero_local": 1,
            "bloque": texto_examen
        }]

    return preguntas_limpias


def extraer_valor_pregunta(bloque: str):
    patrones = [
        r"Puntos\s+indicados\s+en\s+la\s+pregunta\s*:\s*([0-9]+(?:[.,][0-9]+)?)",
        r"\(\s*([0-9]+(?:[.,][0-9]+)?)\s*punto[s]?\s*\)",
        r"Valor\s*:\s*([0-9]+(?:[.,][0-9]+)?)\s*punto[s]?",
        r"Vale\s*([0-9]+(?:[.,][0-9]+)?)\s*punto[s]?",
    ]

    for patron in patrones:
        match = re.search(patron, bloque, flags=re.IGNORECASE)
        if match:
            valor = normalizar_numero(match.group(1))
            if valor is not None and valor > 0:
                return valor

    return None


def asignar_puntajes(preguntas_raw: list, rubrica: dict) -> list:
    total = float(rubrica["total"])
    cantidad = max(len(preguntas_raw), 1)

    serie1_count = sum(1 for p in preguntas_raw if p["serie"] == "Serie 1")
    serie2_count = sum(1 for p in preguntas_raw if p["serie"] == "Serie 2")

    valores_detectados = []

    for p in preguntas_raw:
        valor_individual = extraer_valor_pregunta(p["bloque"])
        valores_detectados.append(valor_individual)

    suma_valores_individuales = sum(v or 0 for v in valores_detectados)

    usar_valores_individuales = (
        any(v is not None for v in valores_detectados)
        and abs(suma_valores_individuales - total) <= max(1, total * 0.10)
    )

    preguntas = []

    for idx, p in enumerate(preguntas_raw, start=1):
        serie = p["serie"]
        valor_individual = valores_detectados[idx - 1]

        if usar_valores_individuales and valor_individual is not None:
            valor = valor_individual

        elif rubrica["serie1"] is not None or rubrica["serie2"] is not None:
            if serie == "Serie 1" and serie1_count > 0:
                valor = float(rubrica["serie1"]) / serie1_count
            elif serie == "Serie 2" and serie2_count > 0:
                valor = float(rubrica["serie2"]) / serie2_count
            else:
                valor = total / cantidad

        else:
            valor = total / cantidad

        preguntas.append(PreguntaExamen(
            id_global=idx,
            serie=serie,
            numero_local=p["numero_local"],
            bloque=p["bloque"],
            valor=round(valor, 2)
        ))

    return preguntas


def construir_tabla_rubrica(preguntas: list, rubrica: dict) -> str:
    filas = [
        f"Pregunta global {p.id_global} | {p.serie} | Pregunta {p.numero_local}: valor máximo {p.valor} puntos"
        for p in preguntas
    ]

    suma = round(sum(p.valor for p in preguntas), 2)

    return f"""
Fuente de puntuación: {rubrica["fuente"]}
Serie 1: {rubrica["serie1"] if rubrica["serie1"] is not None else "No especificado"}
Serie 2: {rubrica["serie2"] if rubrica["serie2"] is not None else "No especificado"}
Total del examen detectado: {rubrica["total"]}
Suma real de valores por pregunta: {suma}

Distribución por pregunta:
{chr(10).join(filas)}
"""


# ============================================================
# RAG
# ============================================================

def dividir_en_chunks(texto: str, tamano_chunk=900, solapamiento=120) -> list:
    texto = " ".join(texto.split())

    if not texto:
        return []

    chunks = []
    inicio = 0

    while inicio < len(texto):
        chunk = texto[inicio:inicio + tamano_chunk].strip()

        if chunk:
            chunks.append(chunk)

        inicio += tamano_chunk - solapamiento

    return chunks


def construir_rag_cache(rutas_contexto: list, texto_contexto: str):
    cache_id = hash_archivos(rutas_contexto)
    carpeta_cache = RAG_DIR / cache_id
    carpeta_cache.mkdir(exist_ok=True)

    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    client = chromadb.PersistentClient(path=str(carpeta_cache))

    collection = client.get_or_create_collection(
        name=f"contexto_{cache_id[:20]}",
        embedding_function=embedding_function
    )

    try:
        cantidad = collection.count()
    except Exception:
        cantidad = 0

    if cantidad == 0:
        print("🔨 Construyendo RAG por primera vez...")

        chunks = dividir_en_chunks(texto_contexto)

        if not chunks:
            return None

        collection.add(
            documents=chunks,
            ids=[f"chunk_{i}" for i in range(len(chunks))],
            metadatas=[{"indice": i} for i in range(len(chunks))]
        )

    else:
        print("✅ RAG desde cache.")

    return collection


def recuperar_contexto_pregunta(
    collection,
    pregunta: PreguntaExamen,
    n_resultados=2,
    limite_caracteres=2200
) -> str:
    if collection is None:
        return ""

    try:
        cantidad = collection.count()
        n = min(n_resultados, cantidad)

        query = re.sub(r"\s+", " ", pregunta.bloque).strip()[:650]

        resultados = collection.query(
            query_texts=[query],
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
        print(f"Error recuperando contexto: {e}")
        return ""


def construir_contexto_por_pregunta(collection, preguntas: list) -> str:
    secciones = []

    for p in preguntas:
        contexto = recuperar_contexto_pregunta(collection, p)

        if not contexto:
            contexto = "No se encontró contexto suficiente."

        secciones.append(f"""
========================
PREGUNTA GLOBAL {p.id_global}
{p.serie} - Pregunta {p.numero_local}
VALOR MÁXIMO: {p.valor} puntos
========================

PREGUNTA Y RESPUESTA:
{p.bloque}

CONTEXTO RELEVANTE:
{contexto}
""")

    return "\n".join(secciones).strip()


# ============================================================
# PAQUETE DE EVALUACIÓN
# ============================================================

def preparar_paquete_evaluacion(ruta_imagen: str, rutas_contexto: list) -> dict:
    imagen_hash = hash_archivo(ruta_imagen)
    contexto_hash = hash_archivos(rutas_contexto)
    paquete_hash = hashlib.sha256(
        f"{imagen_hash}_{contexto_hash}".encode()
    ).hexdigest()

    cache_name = f"paquete_{paquete_hash}.json"

    cache = cargar_json_cache(cache_name)

    if cache:
        print("✅ Paquete desde cache.")
        preguntas = [PreguntaExamen(**p) for p in cache["preguntas"]]

        return {
            "texto_examen": cache["texto_examen"],
            "rubrica": cache["rubrica"],
            "preguntas": preguntas,
            "tabla_rubrica": cache["tabla_rubrica"],
            "contexto_por_pregunta": cache["contexto_por_pregunta"]
        }

    texto_examen = extraer_texto_imagen_gemini(ruta_imagen)

    if not texto_examen.strip():
        return {"error": "No se pudo extraer texto del examen usando Gemini."}

    if "NO HAY EXAMEN LEGIBLE" in texto_examen.upper():
        return {"error": "No se pudo leer un examen válido en la imagen."}

    texto_contexto = leer_contextos(rutas_contexto)

    if not texto_contexto.strip():
        return {"error": "Los archivos de contexto no contienen texto útil."}

    preguntas_raw = dividir_preguntas_con_series(texto_examen)

    if not preguntas_raw:
        return {"error": "No se detectaron preguntas en el examen."}

    rubrica = detectar_rubrica(texto_examen)
    preguntas = asignar_puntajes(preguntas_raw, rubrica)
    tabla_rubrica = construir_tabla_rubrica(preguntas, rubrica)

    collection = construir_rag_cache(rutas_contexto, texto_contexto)

    if collection is None:
        return {"error": "No se pudo construir o cargar el RAG del material."}

    contexto_por_pregunta = construir_contexto_por_pregunta(collection, preguntas)

    data_cache = {
        "texto_examen": texto_examen,
        "rubrica": rubrica,
        "preguntas": [asdict(p) for p in preguntas],
        "tabla_rubrica": tabla_rubrica,
        "contexto_por_pregunta": contexto_por_pregunta
    }

    guardar_json_cache(cache_name, data_cache)

    return {
        "texto_examen": texto_examen,
        "rubrica": rubrica,
        "preguntas": preguntas,
        "tabla_rubrica": tabla_rubrica,
        "contexto_por_pregunta": contexto_por_pregunta
    }


# ============================================================
# DIFICULTAD
# ============================================================

def obtener_criterio_dificultad(nivel: int) -> str:
    return f"""
Nivel seleccionado: {nivel}/10

ESCALA:
1 = Modo amigo extremo.
2 = Muy indulgente.
3 = Flexible.
4 = Moderadamente flexible.
5 = Estándar justo.
6 = Estándar exigente.
7 = Estricto.
8 = Muy estricto.
9 = Experto.
10 = Experto riguroso.

REGLAS POR NIVEL:
- Nivel 1-2: si la idea principal está, otorga casi todo el puntaje.
- Nivel 3-4: acepta respuestas breves si el concepto central es correcto.
- Nivel 5: idea central correcta = Correcta o Parcial alta. No exijas tecnicismos exactos.
- Nivel 6: exige concepto correcto y algo de precisión.
- Nivel 7: exige precisión, permite parciales justos.
- Nivel 8: penaliza omisiones importantes.
- Nivel 9-10: exige definición técnica, precisión, completitud y explicación suficiente.

RANGOS PARA RESPUESTAS PARCIALES:
- Nivel 1-2: parcial = 70-95%.
- Nivel 3-4: parcial = 60-90%.
- Nivel 5-6: parcial = 50-85%.
- Nivel 7-8: parcial = 35-75%.
- Nivel 9-10: parcial = 20-60%.

REGLAS ESPECIALES PARA NIVEL 9-10:
- No otorgues 100% solo porque la idea general esté correcta.
- Si la pregunta pide explicar, relacionar, justificar, mencionar y describir, o responder ampliamente, una respuesta muy breve debe ser Parcial alta, no Correcta completa.
- Si la respuesta no incluye detalles técnicos importantes, ejemplos o explicación suficiente, baja puntos.
- Para otorgar puntaje completo, la respuesta debe ser correcta, completa, específica, clara y técnicamente precisa.
- Si solo menciona elementos pero no los describe, no debe obtener puntaje completo.
- Si falta una parte de una pregunta compuesta, debe ser Parcial.
- En nivel 10, sé riguroso pero justo.

IMPORTANTE:
Si el RAG no recupera una definición clara, usa conocimiento académico general siempre que no contradiga el material.
No califiques nivel {nivel} como si fuera otro nivel.
"""


# ============================================================
# CALIFICACIÓN
# ============================================================

def calificar_paquete(paquete: dict, nivel_dificultad: int) -> str:
    rubrica = paquete["rubrica"]
    texto_examen = paquete["texto_examen"]
    tabla_rubrica = paquete["tabla_rubrica"]
    contexto_por_pregunta = paquete["contexto_por_pregunta"]
    criterio = obtener_criterio_dificultad(nivel_dificultad)

    prompt = f"""
Eres un DOCENTE CALIFICADOR PROFESIONAL.
Califica este examen con precisión y justicia académica.

Usa exactamente:
1. El texto extraído del examen.
2. La rúbrica calculada.
3. El contexto RAG por pregunta.
4. El nivel de dificultad indicado.

========================
EXAMEN EXTRAÍDO
========================
{texto_examen}

========================
RÚBRICA CALCULADA
========================
{tabla_rubrica}

========================
CONTEXTO POR PREGUNTA
========================
{contexto_por_pregunta}

========================
DIFICULTAD
========================
{criterio}

REGLAS OBLIGATORIAS:
- Usa exactamente el total de la rúbrica: {rubrica["total"]}.
- No inventes preguntas.
- No inventes respuestas.
- No cambies el valor máximo de cada pregunta.
- No redistribuyas puntos si ya hay valor por pregunta.
- No califiques sobre más de {rubrica["total"]}.
- Diferencia pregunta global y pregunta local.
- Al final convierte a escala de 100.
- Si el nivel es 5, una respuesta con idea central correcta puede ser Correcta aunque falten tecnicismos.
- Si el nivel es 9 o 10, no otorgues puntaje completo a respuestas demasiado breves cuando la pregunta pide explicar, justificar, relacionar, mencionar y describir, o responder ampliamente.
- En nivel 9 o 10, una respuesta correcta pero breve debe ser Parcial alta, salvo que la pregunta sea solo una definición corta y la definición esté completa.
- Si la pregunta pide varios elementos y falta uno, debe ser Parcial.
- Si la pregunta pide “mencione y describa”, no basta con solo mencionar; debe haber descripción.
- Si el RAG no trae definición clara, usa conocimiento académico general si no contradice el material, pero califica con cautela.
- El estado “Correcta” solo debe usarse cuando la respuesta cubre la idea central y los elementos principales esperados.
- En nivel 10, para dar el 100% del valor, la respuesta debe ser técnica, clara, completa y específica.
- No regales puntos por respuestas vagas.
- Si una respuesta es parcialmente correcta, asigna una puntuación proporcional al valor máximo de esa pregunta.

FORMATO FINAL OBLIGATORIO.
Responde SOLO en Markdown:

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

Repite el bloque anterior para cada pregunta.

## Clasificación Final

**Buenas:** ...

**Parciales:** ...

**Incorrectas:** ...

## Conclusión General

...

## Recomendaciones de Estudio

...
"""

    reporte = llamar_gemini(prompt)

    if not reporte.strip():
        return "ERROR: Gemini terminó, pero no devolvió un reporte válido."

    return reporte


# ============================================================
# FUNCIÓN PARA APP.PY
# ============================================================

def calificar_examen_ui(ruta_imagen: str, rutas_contexto: list, nivel_dificultad: int) -> str:
    paquete = preparar_paquete_evaluacion(ruta_imagen, rutas_contexto)

    if "error" in paquete:
        return paquete["error"]

    return calificar_paquete(paquete, nivel_dificultad)