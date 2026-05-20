import os
import re
import hashlib
import tempfile
import streamlit as st
import plotly.graph_objects as go

from main import preparar_paquete_evaluacion, calificar_paquete


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="EvaluaIA Neural",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CSS PREMIUM
# ============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background:
        radial-gradient(circle at 10% 10%, rgba(59,130,246,0.20), transparent 35%),
        radial-gradient(circle at 90% 5%, rgba(168,85,247,0.20), transparent 35%),
        radial-gradient(circle at 50% 90%, rgba(14,165,233,0.12), transparent 45%),
        linear-gradient(135deg, #020617 0%, #0f172a 50%, #111827 100%);
    color: #e5e7eb;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

hr {
    border-color: rgba(148,163,184,0.18);
}

.hero {
    position: relative;
    overflow: hidden;
    border-radius: 32px;
    padding: 38px;
    margin-bottom: 24px;
    border: 1px solid rgba(125,211,252,0.28);
    background:
        linear-gradient(135deg, rgba(15,23,42,0.94), rgba(30,41,59,0.78)),
        radial-gradient(circle at 20% 20%, rgba(59,130,246,0.30), transparent 35%),
        radial-gradient(circle at 90% 10%, rgba(168,85,247,0.26), transparent 38%);
    box-shadow: 0 30px 90px rgba(0,0,0,0.48);
}

.hero::before {
    content: "";
    position: absolute;
    inset: -2px;
    background: linear-gradient(90deg, transparent, rgba(125,211,252,0.18), transparent);
    transform: translateX(-100%);
    animation: shine 5s infinite;
}

@keyframes shine {
    0% { transform: translateX(-100%); }
    55% { transform: translateX(120%); }
    100% { transform: translateX(120%); }
}

.hero-title {
    position: relative;
    font-size: 56px;
    line-height: 1;
    font-weight: 900;
    letter-spacing: -1.6px;
    background: linear-gradient(90deg, #93c5fd, #c4b5fd, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.hero-sub {
    position: relative;
    margin-top: 14px;
    max-width: 930px;
    color: #cbd5e1;
    font-size: 18px;
    line-height: 1.55;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 14px;
    margin: 16px 8px 0 0;
    border-radius: 999px;
    color: #dbeafe;
    background: rgba(37,99,235,0.15);
    border: 1px solid rgba(96,165,250,0.35);
    font-size: 13px;
    font-weight: 800;
}

.card {
    border-radius: 26px;
    padding: 22px;
    min-height: 145px;
    border: 1px solid rgba(148,163,184,0.20);
    background:
        linear-gradient(180deg, rgba(15,23,42,0.88), rgba(2,6,23,0.72));
    box-shadow: 0 18px 48px rgba(0,0,0,0.30);
}

.card:hover {
    transform: translateY(-2px);
    border-color: rgba(125,211,252,0.45);
    box-shadow: 0 24px 60px rgba(0,0,0,0.40);
    transition: 0.2s ease;
}

.card-label {
    color: #93c5fd;
    font-size: 13px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: .10em;
}

.card-value {
    margin-top: 8px;
    color: #f8fafc;
    font-size: 30px;
    font-weight: 900;
}

.card-desc {
    margin-top: 8px;
    color: #94a3b8;
    font-size: 14px;
    line-height: 1.45;
}

.glass {
    border-radius: 28px;
    padding: 24px;
    border: 1px solid rgba(148,163,184,0.20);
    background: rgba(15,23,42,0.62);
    box-shadow: 0 18px 55px rgba(0,0,0,0.28);
}

.upload-box {
    border-radius: 24px;
    padding: 22px;
    border: 1px dashed rgba(125,211,252,0.38);
    background:
        linear-gradient(180deg, rgba(15,23,42,0.72), rgba(30,41,59,0.38));
    margin-bottom: 14px;
}

.section-title {
    font-size: 28px;
    font-weight: 900;
    color: #f8fafc;
    margin: 12px 0 6px 0;
}

.section-sub {
    color: #94a3b8;
    margin-bottom: 16px;
}

.difficulty {
    border-radius: 24px;
    padding: 20px;
    margin-top: 12px;
    border: 1px solid rgba(148,163,184,0.22);
    font-weight: 800;
}

.diff-green { background: rgba(34,197,94,0.15); color: #bbf7d0; border-color: rgba(34,197,94,0.35); }
.diff-yellow { background: rgba(234,179,8,0.15); color: #fef3c7; border-color: rgba(234,179,8,0.35); }
.diff-blue { background: rgba(59,130,246,0.15); color: #bfdbfe; border-color: rgba(59,130,246,0.35); }
.diff-orange { background: rgba(249,115,22,0.15); color: #fed7aa; border-color: rgba(249,115,22,0.35); }
.diff-red { background: rgba(239,68,68,0.15); color: #fecaca; border-color: rgba(239,68,68,0.35); }

.stButton > button {
    width: 100%;
    border-radius: 18px;
    padding: 15px 18px;
    font-size: 17px;
    font-weight: 900;
    color: white;
    border: 1px solid rgba(125,211,252,0.45);
    background: linear-gradient(90deg, #2563eb, #7c3aed);
    box-shadow: 0 15px 36px rgba(37,99,235,0.26);
}

.stButton > button:hover {
    transform: translateY(-1px);
    border-color: rgba(125,211,252,0.85);
    box-shadow: 0 20px 50px rgba(124,58,237,0.34);
}

.stDownloadButton > button {
    width: 100%;
    border-radius: 18px;
    padding: 14px 18px;
    font-weight: 900;
    color: white;
    background: linear-gradient(90deg, #0f766e, #2563eb);
    border: 1px solid rgba(125,211,252,0.35);
}

div[data-testid="stFileUploader"] section {
    background: rgba(2,6,23,0.45);
    border: 1px dashed rgba(125,211,252,0.35);
    border-radius: 18px;
}

.result-shell {
    border-radius: 30px;
    padding: 26px;
    border: 1px solid rgba(148,163,184,0.22);
    background:
        linear-gradient(180deg, rgba(15,23,42,0.88), rgba(2,6,23,0.72));
    box-shadow: 0 22px 72px rgba(0,0,0,0.38);
}

.question-card {
    border-radius: 22px;
    padding: 20px;
    border: 1px solid rgba(148,163,184,0.16);
    background: rgba(15,23,42,0.68);
}

.status-chip {
    display: inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(59,130,246,0.16);
    border: 1px solid rgba(96,165,250,0.32);
    color: #dbeafe;
    font-weight: 800;
    font-size: 13px;
}

.loading-card {
    border-radius: 24px;
    padding: 18px 20px;
    border: 1px solid rgba(96,165,250,0.28);
    background: rgba(15,23,42,0.76);
    color: #dbeafe;
    font-weight: 800;
    box-shadow: 0 0 35px rgba(59,130,246,0.16);
}

.small {
    color: #94a3b8;
    font-size: 13px;
}

.footer-note {
    color: #64748b;
    font-size: 13px;
    text-align: center;
    padding-top: 18px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "paquete_cache": None,
    "ultimo_hash": None,
    "ultimo_resultado": None,
    "ultima_dificultad": 5,
    "mostrar_resultado": False,
    "contextos_bytes": [],
    "imagen_bytes": None,
    "ultimo_resumen": {},
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# FUNCIONES
# ============================================================

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def limpiar_markdown(texto: str) -> str:
    return (
        str(texto)
        .replace("```markdown", "")
        .replace("```", "")
        .strip()
    )


def guardar_archivo_temporal(temp_dir, nombre, data):
    ruta = os.path.join(temp_dir, nombre)
    with open(ruta, "wb") as f:
        f.write(data)
    return ruta


def extraer_numero(patron, texto, default=None):
    match = re.search(patron, texto, flags=re.IGNORECASE)
    if not match:
        return default
    try:
        return float(match.group(1).replace(",", "."))
    except Exception:
        return default


def extraer_entero(patron, texto, default=0):
    match = re.search(patron, texto, flags=re.IGNORECASE)
    if not match:
        return default
    try:
        return int(float(match.group(1).replace(",", ".")))
    except Exception:
        return default


def extraer_resumen(resultado: str) -> dict:
    texto = limpiar_markdown(resultado)

    obtenido = extraer_numero(r"Punteo obtenido:\*\*\s*([0-9]+(?:[.,][0-9]+)?)", texto, None)
    total = extraer_numero(r"Punteo obtenido:\*\*\s*[0-9]+(?:[.,][0-9]+)?\s*/\s*([0-9]+(?:[.,][0-9]+)?)", texto, None)
    nota = extraer_numero(r"Nota final en escala de 100:\*\*\s*([0-9]+(?:[.,][0-9]+)?)", texto, None)
    nivel = extraer_entero(r"Nivel de dificultad aplicado:\*\*\s*([0-9]+)", texto, st.session_state.ultima_dificultad)

    buenas = extraer_entero(r"Buenas:\*\*\s*([0-9]+)", texto, 0)
    parciales = extraer_entero(r"Parciales:\*\*\s*([0-9]+)", texto, 0)
    incorrectas = extraer_entero(r"Incorrectas:\*\*\s*([0-9]+)", texto, 0)

    return {
        "obtenido": obtenido,
        "total": total,
        "nota": nota,
        "nivel": nivel,
        "buenas": buenas,
        "parciales": parciales,
        "incorrectas": incorrectas,
    }


def dificultad_info(nivel: int):
    if nivel <= 2:
        return "Muy flexible", "Prioriza acercamiento e intención de respuesta.", "diff-green", "🟢"
    if nivel <= 4:
        return "Flexible", "Acepta respuestas breves si capturan la idea central.", "diff-yellow", "🟡"
    if nivel <= 6:
        return "Estándar académico", "Balance entre justicia, comprensión y precisión.", "diff-blue", "🔵"
    if nivel <= 8:
        return "Estricto", "Penaliza omisiones, vaguedad y falta de desarrollo.", "diff-orange", "🟠"
    return "Experto riguroso", "Exige precisión técnica, completitud y profundidad.", "diff-red", "🔴"


def card(label, value, desc, icon="🧠"):
    st.markdown(
        f"""
        <div class="card">
            <div class="card-label">{icon} {label}</div>
            <div class="card-value">{value}</div>
            <div class="card-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def metric_card(label, value, desc):
    st.markdown(
        f"""
        <div class="card">
            <div class="card-label">{label}</div>
            <div class="card-value">{value}</div>
            <div class="card-desc">{desc}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def crear_gauge(nota):
    nota = nota or 0
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=nota,
            number={"suffix": "/100", "font": {"size": 36, "color": "#f8fafc"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#94a3b8"},
                "bar": {"color": "#60a5fa"},
                "bgcolor": "rgba(15,23,42,0.55)",
                "borderwidth": 1,
                "bordercolor": "rgba(148,163,184,0.35)",
                "steps": [
                    {"range": [0, 60], "color": "rgba(239,68,68,0.25)"},
                    {"range": [60, 80], "color": "rgba(245,158,11,0.25)"},
                    {"range": [80, 100], "color": "rgba(34,197,94,0.25)"},
                ],
            },
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb"),
    )
    return fig


def crear_donut(buenas, parciales, incorrectas):
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Buenas", "Parciales", "Incorrectas"],
                values=[buenas, parciales, incorrectas],
                hole=0.62,
                textinfo="label+value",
                marker=dict(colors=["#22c55e", "#f59e0b", "#ef4444"]),
            )
        ]
    )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5e7eb", size=14),
        showlegend=False,
    )
    return fig


def separar_preguntas(resultado: str):
    texto = limpiar_markdown(resultado)
    partes = re.split(r"(?=### Pregunta global\s+\d+)", texto)
    intro = partes[0].strip() if partes else ""
    preguntas = [p.strip() for p in partes[1:] if p.strip()]
    return intro, preguntas


def estado_pregunta(bloque: str):
    if "Estado:** Correcta" in bloque or "Estado: Correcta" in bloque:
        return "✅"
    if "Estado:** Parcial" in bloque or "Estado: Parcial" in bloque:
        return "🟡"
    if "Estado:** Incorrecta" in bloque or "Estado: Incorrecta" in bloque:
        return "❌"
    return "🧠"


# ============================================================
# MODALES FUNCIONALES
# ============================================================

if hasattr(st, "dialog"):

    @st.dialog("🧠 Arquitectura inteligente")
    def modal_arquitectura():
        st.markdown("""
        ### Pipeline de EvaluaIA Neural

        **1. OCR/ICR Vision**  
        Lee la imagen del examen, detecta preguntas, respuestas y rúbrica.

        **2. RAG Contextual**  
        Busca fragmentos relevantes en los documentos del profesor.

        **3. LLM Calificador**  
        Compara respuesta del estudiante contra material y conocimiento académico.

        **4. Dificultad Adaptativa**  
        Ajusta la exigencia de 1 a 10.

        **5. Informe Académico**  
        Genera punteo, justificación, retroalimentación y recomendaciones.
        """)

    @st.dialog("📘 Guía rápida")
    def modal_guia():
        st.markdown("""
        ### Cómo usar el sistema

        1. Sube uno o varios **materiales de referencia**.
        2. Sube la **imagen del examen resuelto**.
        3. Selecciona el nivel de dificultad.
        4. Presiona **Ejecutar análisis inteligente**.
        5. Revisa el dashboard y el detalle por pregunta.

        **Recomendación:** usa imágenes claras, con buena luz y sin cortes.
        """)


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">EvaluaIA Neural</div>
        <div class="hero-sub">
            Plataforma inteligente de calificación académica con visión artificial, recuperación aumentada,
            rúbrica automática y evaluación adaptable por dificultad.
        </div>
        <div>
            <span class="badge">👁️ OCR/ICR Vision</span>
            <span class="badge">📚 RAG Contextual</span>
            <span class="badge">🧠 LLM Calificador</span>
            <span class="badge">🎯 Dificultad 1–10</span>
            <span class="badge">📊 Dashboard automático</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# BOTONES MODALES FUNCIONALES
# ============================================================

b1, b2, b3 = st.columns([1, 1, 2])

with b1:
    if st.button("🧠 Ver arquitectura IA"):
        if hasattr(st, "dialog"):
            modal_arquitectura()
        else:
            st.info("OCR/ICR → RAG → LLM → Rúbrica → Reporte")

with b2:
    if st.button("📘 Guía rápida"):
        if hasattr(st, "dialog"):
            modal_guia()
        else:
            st.info("Sube material, sube examen, elige dificultad y califica.")

with b3:
    st.markdown(
        """
        <div class="glass">
            <span class="status-chip">Sistema listo</span>
            <span class="small"> · Esperando materiales y examen para iniciar el análisis.</span>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# TARJETAS
# ============================================================

st.divider()

c1, c2, c3, c4 = st.columns(4)

with c1:
    card("Materiales", str(len(st.session_state.contextos_bytes)), "Documentos usados como base de conocimiento.", "📚")

with c2:
    card("Examen", "Listo" if st.session_state.imagen_bytes else "Pendiente", "Imagen del examen del estudiante.", "📝")

with c3:
    card("Motor IA", "OCR + RAG + LLM", "Procesamiento visual y evaluación contextual.", "⚡")

with c4:
    card("Reporte", "Automático", "Punteo, justificación y recomendaciones.", "📑")


# ============================================================
# CARGA
# ============================================================

st.markdown('<div class="section-title">📥 Carga de archivos</div>', unsafe_allow_html=True)
st.markdown('<div class="section-sub">Sube el material del profesor y la imagen del examen. El sistema detectará preguntas, respuestas y valores de la rúbrica.</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        <div class="upload-box">
            <h3>📚 Materiales de referencia</h3>
            <p style="color:#94a3b8;">PDF, DOCX, TXT o MD. Estos documentos alimentan el RAG.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    archivos_contexto = st.file_uploader(
        "Materiales",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        key="uploader_contextos",
        label_visibility="collapsed"
    )

with col2:
    st.markdown(
        """
        <div class="upload-box">
            <h3>📝 Examen del estudiante</h3>
            <p style="color:#94a3b8;">Imagen clara en PNG, JPG o JPEG.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    imagen_examen = st.file_uploader(
        "Examen",
        type=["png", "jpg", "jpeg"],
        key="uploader_imagen",
        label_visibility="collapsed"
    )


if archivos_contexto:
    st.session_state.contextos_bytes = [
        {"name": archivo.name, "bytes": archivo.getvalue()}
        for archivo in archivos_contexto
    ]

if imagen_examen:
    st.session_state.imagen_bytes = {
        "name": imagen_examen.name,
        "bytes": imagen_examen.getvalue()
    }


# ============================================================
# PREVIEW
# ============================================================

p1, p2 = st.columns(2)

with p1:
    st.markdown("### 📚 Material cargado")
    if st.session_state.contextos_bytes:
        for archivo in st.session_state.contextos_bytes:
            size_kb = len(archivo["bytes"]) / 1024
            st.success(f"{archivo['name']} · {size_kb:.1f} KB")
    else:
        st.info("Aún no has subido material de referencia.")

with p2:
    st.markdown("### 🖼️ Vista previa del examen")
    if st.session_state.imagen_bytes:
        st.image(st.session_state.imagen_bytes["bytes"])
    else:
        st.info("Aún no has subido la imagen del examen.")


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.divider()
st.markdown('<div class="section-title">⚙️ Configuración de calificación</div>', unsafe_allow_html=True)

nivel_dificultad = st.slider(
    "Nivel de dificultad",
    min_value=1,
    max_value=10,
    value=st.session_state.ultima_dificultad,
    step=1
)

st.session_state.ultima_dificultad = nivel_dificultad

modo, descripcion, clase, icono = dificultad_info(nivel_dificultad)

st.markdown(
    f"""
    <div class="difficulty {clase}">
        {icono} <strong>{modo}</strong> · Nivel {nivel_dificultad}/10
        <br>
        <span style="font-weight:600;">{descripcion}</span>
    </div>
    """,
    unsafe_allow_html=True
)

mostrar_extraccion = st.checkbox("🔎 Mostrar extracción OCR después del análisis", value=False)


# ============================================================
# BOTONES DE ACCIÓN
# ============================================================

st.divider()

a1, a2 = st.columns([4, 1])

with a1:
    iniciar = st.button("🚀 Ejecutar análisis inteligente")

with a2:
    limpiar = st.button("🗑️ Reiniciar")


if limpiar:
    st.session_state.paquete_cache = None
    st.session_state.ultimo_hash = None
    st.session_state.ultimo_resultado = None
    st.session_state.mostrar_resultado = False
    st.session_state.contextos_bytes = []
    st.session_state.imagen_bytes = None
    st.session_state.ultimo_resumen = {}
    st.rerun()


# ============================================================
# PROCESO
# ============================================================

if iniciar:

    if not st.session_state.contextos_bytes:
        st.warning("Debes subir al menos un archivo de referencia.")
        st.stop()

    if st.session_state.imagen_bytes is None:
        st.warning("Debes subir la imagen del examen.")
        st.stop()

    try:
        hash_actual = hash_bytes(st.session_state.imagen_bytes["bytes"])

        for archivo in st.session_state.contextos_bytes:
            hash_actual += hash_bytes(archivo["bytes"])

        hash_actual = hashlib.sha256(hash_actual.encode()).hexdigest()

        reutilizar_cache = (
            st.session_state.paquete_cache is not None
            and st.session_state.ultimo_hash == hash_actual
        )

        progress = st.progress(0)
        estado = st.empty()

        with tempfile.TemporaryDirectory() as temp_dir:

            estado.markdown('<div class="loading-card">🧩 Preparando archivos temporales...</div>', unsafe_allow_html=True)
            progress.progress(10)

            ruta_imagen = guardar_archivo_temporal(
                temp_dir,
                st.session_state.imagen_bytes["name"],
                st.session_state.imagen_bytes["bytes"]
            )

            rutas_contexto = []

            for archivo in st.session_state.contextos_bytes:
                ruta = guardar_archivo_temporal(
                    temp_dir,
                    archivo["name"],
                    archivo["bytes"]
                )
                rutas_contexto.append(ruta)

            if reutilizar_cache:
                estado.markdown('<div class="loading-card">♻️ Reutilizando OCR y RAG procesados...</div>', unsafe_allow_html=True)
                progress.progress(55)
                paquete = st.session_state.paquete_cache

            else:
                estado.markdown('<div class="loading-card">👁️ Leyendo imagen con OCR/ICR y detectando rúbrica...</div>', unsafe_allow_html=True)
                progress.progress(25)

                with st.spinner("Procesando visión y contexto..."):
                    paquete = preparar_paquete_evaluacion(
                        ruta_imagen,
                        rutas_contexto
                    )

                progress.progress(68)

                if "error" in paquete:
                    st.error(paquete["error"])
                    st.stop()

                st.session_state.paquete_cache = paquete
                st.session_state.ultimo_hash = hash_actual

            if mostrar_extraccion:
                with st.expander("📄 Texto extraído del examen"):
                    st.text(paquete.get("texto_examen", ""))

            estado.markdown('<div class="loading-card">📚 Comparando respuestas contra el material de referencia...</div>', unsafe_allow_html=True)
            progress.progress(78)

            with st.spinner("Calificando con IA..."):
                resultado = calificar_paquete(
                    paquete,
                    nivel_dificultad
                )

            estado.markdown('<div class="loading-card">📑 Generando informe académico y dashboard...</div>', unsafe_allow_html=True)
            progress.progress(92)

            resultado = limpiar_markdown(resultado)

            if not resultado:
                st.error("La IA terminó, pero no devolvió un reporte válido.")
                st.stop()

            st.session_state.ultimo_resultado = resultado
            st.session_state.ultimo_resumen = extraer_resumen(resultado)
            st.session_state.mostrar_resultado = True

            progress.progress(100)
            estado.markdown('<div class="loading-card">✅ Evaluación completada.</div>', unsafe_allow_html=True)

            st.rerun()

    except Exception as e:
        st.error(f"Error general:\n\n{str(e)}")


# ============================================================
# RESULTADOS
# ============================================================

if st.session_state.mostrar_resultado and st.session_state.ultimo_resultado:

    resultado_limpio = limpiar_markdown(st.session_state.ultimo_resultado)
    resumen = st.session_state.ultimo_resumen or extraer_resumen(resultado_limpio)

    obtenido = resumen.get("obtenido")
    total = resumen.get("total")
    nota = resumen.get("nota")
    buenas = resumen.get("buenas", 0)
    parciales = resumen.get("parciales", 0)
    incorrectas = resumen.get("incorrectas", 0)
    nivel = resumen.get("nivel", nivel_dificultad)

    st.divider()
    st.markdown('<div class="section-title">📊 Dashboard de resultados</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Resumen visual generado automáticamente por la IA.</div>', unsafe_allow_html=True)

    r1, r2, r3, r4, r5 = st.columns(5)

    with r1:
        metric_card("Punteo", f"{obtenido:g}/{total:g}" if obtenido is not None and total else "—", "Punteo detectado")
    with r2:
        metric_card("Nota", f"{nota:g}/100" if nota is not None else "—", "Escala final")
    with r3:
        metric_card("Buenas", str(buenas), "Respuestas correctas")
    with r4:
        metric_card("Parciales", str(parciales), "Respuestas incompletas")
    with r5:
        metric_card("Incorrectas", str(incorrectas), "Respuestas malas")

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("### 🎯 Medidor de nota")
        st.plotly_chart(crear_gauge(nota), use_container_width=True)

    with g2:
        st.markdown("### 🧬 Distribución de respuestas")
        st.plotly_chart(crear_donut(buenas, parciales, incorrectas), use_container_width=True)

    st.markdown(
        f"""
        <div class="result-shell">
            <h2>📑 Informe de Calificación</h2>
            <p style="color:#94a3b8;">Nivel aplicado: {nivel}/10 · Motor: OCR/ICR + RAG + LLM</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    intro, preguntas = separar_preguntas(resultado_limpio)

    with st.expander("📌 Resumen general", expanded=True):
        st.markdown(intro)

    if preguntas:
        st.markdown("### 🧾 Detalle por pregunta")

        for i, bloque in enumerate(preguntas, start=1):
            icono_estado = estado_pregunta(bloque)
            titulo = f"Pregunta global {i}"

            match_titulo = re.search(r"###\s*(Pregunta global\s+\d+)", bloque, flags=re.IGNORECASE)
            if match_titulo:
                titulo = match_titulo.group(1)

            with st.expander(f"{icono_estado} {titulo}", expanded=False):
                st.markdown('<div class="question-card">', unsafe_allow_html=True)
                st.markdown(bloque)
                st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("📄 Ver informe completo", expanded=False):
        st.markdown(resultado_limpio)

    st.download_button(
        label="⬇️ Descargar reporte Markdown",
        data=resultado_limpio,
        file_name="reporte_calificacion.md",
        mime="text/markdown"
    )

else:
    st.divider()
    st.markdown(
        """
        <div class="result-shell">
            <h2>🧠 Esperando examen</h2>
            <p style="color:#94a3b8;">
                Sube el material de referencia y la imagen del examen para iniciar la evaluación inteligente.
            </p>
            <span class="badge">1. Lectura OCR/ICR</span>
            <span class="badge">2. Búsqueda RAG</span>
            <span class="badge">3. Evaluación LLM</span>
            <span class="badge">4. Dashboard final</span>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    """
    <div class="footer-note">
        EvaluaIA Neural · Sistema inteligente de evaluación académica
    </div>
    """,
    unsafe_allow_html=True
)