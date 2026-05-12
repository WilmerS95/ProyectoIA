import os
import tempfile
from pathlib import Path

import streamlit as st

from main import calificar_examen_ui, extraer_texto_imagen


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

st.set_page_config(
    page_title="Calificador de Exámenes IA",
    page_icon="🧠",
    layout="wide"
)


# =========================================================
# SESSION STATE
# =========================================================

if "resultado" not in st.session_state:
    st.session_state.resultado = None

if "texto_extraido" not in st.session_state:
    st.session_state.texto_extraido = None

if "archivos_contexto" not in st.session_state:
    st.session_state.archivos_contexto = []

if "archivo_examen" not in st.session_state:
    st.session_state.archivo_examen = None

if "ultima_dificultad" not in st.session_state:
    st.session_state.ultima_dificultad = 5


# =========================================================
# ESTILOS
# =========================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.stButton > button {
    width: 100%;
    border-radius: 12px;
    height: 3.1rem;
    border: none;
    background: linear-gradient(90deg, #ff4b4b, #ff2e63);
    color: white;
    font-size: 17px;
    font-weight: bold;
}

.stButton > button:hover {
    background: linear-gradient(90deg, #ff2e63, #ff4b4b);
}

.result-box {
    background-color: #0f172a;
    padding: 24px;
    border-radius: 16px;
    border: 1px solid #334155;
    margin-top: 20px;
    line-height: 1.6;
}

.small-muted {
    color: #94a3b8;
    font-size: 14px;
}
</style>
""",
    unsafe_allow_html=True
)


# =========================================================
# ENCABEZADO
# =========================================================

st.title("🧠 Calificador de Exámenes IA")
st.markdown(
    "Sistema inteligente de evaluación automática con análisis contextual, RAG y razonamiento académico."
)

st.divider()


# =========================================================
# SUBIDA DE ARCHIVOS
# =========================================================

col1, col2 = st.columns(2)

with col1:
    st.markdown("## 📚 Materiales de referencia")

    archivos_contexto = st.file_uploader(
        "Sube uno o varios archivos del profesor",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        key="uploader_contexto"
    )

    st.caption("Puedes subir PDFs, documentos TXT, Markdown o DOCX.")

with col2:
    st.markdown("## 🖼️ Examen del estudiante")

    archivo_examen = st.file_uploader(
        "Sube la foto o escaneo del examen",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
        key="uploader_examen"
    )

    st.caption("Formatos permitidos: JPG, JPEG y PNG.")


# =========================================================
# GUARDAR ARCHIVOS EN SESSION_STATE
# =========================================================

if archivos_contexto:
    st.session_state.archivos_contexto = archivos_contexto

if archivo_examen:
    st.session_state.archivo_examen = archivo_examen


# =========================================================
# MOSTRAR ARCHIVOS ACTUALES
# =========================================================

if st.session_state.archivos_contexto or st.session_state.archivo_examen:
    st.markdown("### 📌 Archivos cargados actualmente")

    if st.session_state.archivos_contexto:
        st.write("**Materiales de referencia:**")
        for archivo in st.session_state.archivos_contexto:
            st.write(f"📄 {archivo.name}")

    if st.session_state.archivo_examen:
        st.write("**Examen:**")
        st.write(f"🖼️ {st.session_state.archivo_examen.name}")

st.divider()


# =========================================================
# CONFIGURACIÓN DE CALIFICACIÓN
# =========================================================

st.markdown("## ⚙️ Configuración de Calificación")

nivel_dificultad = st.slider(
    "Nivel de dificultad",
    min_value=1,
    max_value=10,
    value=st.session_state.ultima_dificultad
)

st.session_state.ultima_dificultad = nivel_dificultad

if nivel_dificultad <= 2:
    st.info("Modo muy flexible: acepta ideas generales y conceptos básicos.")

elif nivel_dificultad <= 4:
    st.info("Modo flexible: prioriza comprensión general sobre precisión técnica.")

elif nivel_dificultad <= 6:
    st.info("Modo estándar: exige conceptos correctos y explicación suficiente.")

elif nivel_dificultad <= 8:
    st.warning("Modo estricto: exige precisión conceptual, profundidad y claridad.")

else:
    st.error("Modo muy estricto: evaluación rigurosa y técnica.")

mostrar_ocr = st.checkbox("Mostrar extracción inicial de la imagen")

st.divider()


# =========================================================
# BOTONES
# =========================================================

col_btn1, col_btn2 = st.columns([4, 1])

with col_btn1:
    iniciar = st.button("🚀 Iniciar Calificación Autónoma")

with col_btn2:
    limpiar = st.button("🗑️ Limpiar")


# =========================================================
# LIMPIAR
# =========================================================

if limpiar:
    st.session_state.resultado = None
    st.session_state.texto_extraido = None
    st.session_state.archivos_contexto = []
    st.session_state.archivo_examen = None
    st.rerun()


# =========================================================
# PROCESO PRINCIPAL
# =========================================================

if iniciar:

    if not st.session_state.archivos_contexto:
        st.warning("⚠️ Debes subir al menos un archivo de referencia.")
        st.stop()

    if st.session_state.archivo_examen is None:
        st.warning("⚠️ Debes subir el examen del estudiante.")
        st.stop()

    rutas_contexto = []
    ruta_examen = None

    try:
        with st.spinner("🔎 Analizando examen y material académico..."):

            # Guardar archivos de contexto temporalmente
            for archivo in st.session_state.archivos_contexto:
                archivo.seek(0)
                suffix = Path(archivo.name).suffix

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(archivo.read())
                    rutas_contexto.append(tmp.name)

            # Guardar imagen del examen temporalmente
            st.session_state.archivo_examen.seek(0)
            suffix_exam = Path(st.session_state.archivo_examen.name).suffix

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_exam) as tmp_exam:
                tmp_exam.write(st.session_state.archivo_examen.read())
                ruta_examen = tmp_exam.name

            # OCR opcional
            if mostrar_ocr:
                texto_extraido = extraer_texto_imagen(ruta_examen)
                st.session_state.texto_extraido = texto_extraido

            # Calificación
            resultado = calificar_examen_ui(
                ruta_imagen=ruta_examen,
                rutas_contexto=rutas_contexto,
                nivel_dificultad=nivel_dificultad
            )

            st.session_state.resultado = resultado

        st.success("✅ Calificación completada correctamente.")

    except Exception as e:
        st.error(f"❌ Ocurrió un error durante la calificación:\n\n{e}")

    finally:
        try:
            if ruta_examen and os.path.exists(ruta_examen):
                os.remove(ruta_examen)

            for ruta in rutas_contexto:
                if ruta and os.path.exists(ruta):
                    os.remove(ruta)

        except Exception:
            pass


# =========================================================
# MOSTRAR OCR
# =========================================================

if mostrar_ocr and st.session_state.texto_extraido:
    st.divider()
    st.markdown("## 🧾 Extracción inicial de la imagen")

    st.text_area(
        "Preguntas y respuestas detectadas",
        value=st.session_state.texto_extraido,
        height=350
    )


# =========================================================
# MOSTRAR RESULTADO
# =========================================================

if st.session_state.resultado:
    st.divider()
    st.markdown("## 📑 Informe de Calificación")

    resultado_texto = str(st.session_state.resultado)

    st.markdown(resultado_texto)

    st.download_button(
        label="⬇️ Descargar Reporte",
        data=resultado_texto,
        file_name="reporte_calificacion.md",
        mime="text/markdown",
        width="stretch"
    )