import os
import hashlib
import tempfile
import streamlit as st

from main import preparar_paquete_evaluacion, calificar_paquete


st.set_page_config(
    page_title="Calificador Inteligente IA",
    page_icon="🧠",
    layout="wide"
)


# =========================
# CSS
# =========================

st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.stButton > button {
    width: 100%;
    border-radius: 14px;
    padding: 14px;
    font-size: 18px;
    font-weight: bold;
}

.result-card {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 18px;
    padding: 25px;
    margin-top: 20px;
}
</style>
""", unsafe_allow_html=True)


# =========================
# SESSION STATE
# =========================

defaults = {
    "paquete_cache": None,
    "ultimo_hash": None,
    "ultimo_resultado": None,
    "ultima_dificultad": 5,
    "mostrar_resultado": False,
    "contextos_bytes": [],
    "imagen_bytes": None,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =========================
# FUNCIONES
# =========================

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


# =========================
# HEADER
# =========================

st.markdown("# 🧠 Calificador Inteligente de Exámenes")
st.markdown("OCR/ICR + RAG + IA + dificultad adaptable 1–10")
st.divider()


# =========================
# SUBIDA
# =========================

col1, col2 = st.columns(2)

with col1:
    st.markdown("## 📚 Materiales de referencia")

    archivos_contexto = st.file_uploader(
        "Sube PDFs o documentos del profesor",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        key="uploader_contextos"
    )

with col2:
    st.markdown("## 🖼️ Examen del estudiante")

    imagen_examen = st.file_uploader(
        "Sube una imagen del examen",
        type=["png", "jpg", "jpeg"],
        key="uploader_imagen"
    )


# Guardar bytes para que no se pierdan al mover dificultad
if archivos_contexto:
    st.session_state.contextos_bytes = [
        {
            "name": archivo.name,
            "bytes": archivo.getvalue()
        }
        for archivo in archivos_contexto
    ]

if imagen_examen:
    st.session_state.imagen_bytes = {
        "name": imagen_examen.name,
        "bytes": imagen_examen.getvalue()
    }


st.divider()


# =========================
# CONFIGURACIÓN
# =========================

st.markdown("## ⚙️ Configuración")

nivel_dificultad = st.slider(
    "Nivel de dificultad",
    min_value=1,
    max_value=10,
    value=st.session_state.ultima_dificultad,
    step=1
)

st.session_state.ultima_dificultad = nivel_dificultad

if nivel_dificultad <= 2:
    st.info("🟢 Modo muy flexible")
elif nivel_dificultad <= 4:
    st.info("🟡 Modo flexible")
elif nivel_dificultad <= 6:
    st.info("🔵 Modo estándar académico")
elif nivel_dificultad <= 8:
    st.warning("🟠 Modo estricto")
else:
    st.error("🔴 Modo experto riguroso")

mostrar_extraccion = st.checkbox("Mostrar extracción OCR", value=False)

st.divider()


# =========================
# BOTONES
# =========================

col_btn1, col_btn2 = st.columns([4, 1])

with col_btn1:
    iniciar = st.button("🚀 Calificar Examen")

with col_btn2:
    limpiar = st.button("🗑️ Limpiar")


if limpiar:
    st.session_state.paquete_cache = None
    st.session_state.ultimo_hash = None
    st.session_state.ultimo_resultado = None
    st.session_state.mostrar_resultado = False
    st.session_state.contextos_bytes = []
    st.session_state.imagen_bytes = None
    st.rerun()


# =========================
# PROCESO
# =========================

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

        with tempfile.TemporaryDirectory() as temp_dir:

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
                st.success("♻️ Reutilizando OCR y RAG ya procesados.")
                paquete = st.session_state.paquete_cache

            else:
                with st.spinner("🧠 Procesando OCR, rúbrica y RAG..."):
                    paquete = preparar_paquete_evaluacion(
                        ruta_imagen,
                        rutas_contexto
                    )

                if "error" in paquete:
                    st.error(paquete["error"])
                    st.stop()

                st.session_state.paquete_cache = paquete
                st.session_state.ultimo_hash = hash_actual

            if mostrar_extraccion:
                with st.expander("📄 Texto extraído del examen"):
                    st.text(paquete.get("texto_examen", ""))

            with st.spinner("🤖 Calificando examen con IA..."):
                resultado = calificar_paquete(
                    paquete,
                    nivel_dificultad
                )

            resultado = limpiar_markdown(resultado)

            if not resultado:
                st.error("La IA terminó, pero no devolvió un reporte válido al front.")
                st.stop()

            st.session_state.ultimo_resultado = resultado
            st.session_state.mostrar_resultado = True

            st.rerun()

    except Exception as e:
        st.error(f"Error general:\n\n{str(e)}")


# =========================
# MOSTRAR RESULTADO SIEMPRE FUERA DEL BOTÓN
# =========================

if st.session_state.mostrar_resultado and st.session_state.ultimo_resultado:

    st.divider()

    st.markdown("## 📑 Informe de Calificación")

    resultado_limpio = limpiar_markdown(st.session_state.ultimo_resultado)

    st.markdown(
        '<div class="result-card">',
        unsafe_allow_html=True
    )

    st.markdown(resultado_limpio)

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )

    st.download_button(
        label="⬇️ Descargar Reporte",
        data=resultado_limpio,
        file_name="reporte_calificacion.md",
        mime="text/markdown",
        width="stretch"
    )