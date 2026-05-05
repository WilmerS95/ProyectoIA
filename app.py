import os
import tempfile
from pathlib import Path

import streamlit as st

from main import calificar_examen_ui, extraer_texto_imagen_gemini


st.set_page_config(
    page_title="Calificador de Exámenes IA",
    page_icon="📝",
    layout="wide"
)

st.title("Sistema Inteligente Multimodal para la Calificación Autónoma")

st.markdown(
    """
    Sube uno o varios materiales de clase y una imagen del examen resuelto.
    El sistema analizará la imagen con Gemini, buscará el contexto más relevante con RAG
    y generará una calificación profesional por pregunta.
    """
)

with st.expander("¿Cómo funciona el sistema?", expanded=False):
    st.markdown(
        """
        **Flujo del sistema:**

        1. Gemini lee la imagen del examen y extrae preguntas y respuestas.
        2. Los materiales del profesor se dividen en fragmentos.
        3. RAG busca los fragmentos más relacionados con el examen.
        4. El agente calificador evalúa cada respuesta.
        5. Se genera un informe con puntuación, justificación y retroalimentación.
        """
    )

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Material de Clase")
    archivos_contexto = st.file_uploader(
        "Sube materiales de referencia",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
        help="Puedes subir uno o varios archivos: PDF, TXT, MD o DOCX."
    )

    if archivos_contexto:
        st.caption(f"Archivos cargados: {len(archivos_contexto)}")
        for archivo in archivos_contexto:
            st.write(f"📄 {archivo.name}")

with col2:
    st.subheader("2. Examen del Estudiante")
    archivo_examen = st.file_uploader(
        "Sube la foto o escaneo del examen resuelto",
        type=["jpg", "jpeg", "png"],
        help="Debe ser una imagen clara del examen ya respondido."
    )

    if archivo_examen:
        st.caption(f"Imagen cargada: {archivo_examen.name}")
        st.image(archivo_examen, caption="Vista previa del examen", use_container_width=True)

st.divider()

st.subheader("3. Configuración de Calificación")

dificultad = st.slider(
    "Nivel de dificultad",
    min_value=1,
    max_value=10,
    value=5,
    help="1 = más flexible, 10 = más estricto."
)

if dificultad <= 3:
    st.info(
        "Modo flexible: acepta respuestas equivalentes, errores menores de redacción "
        "y comprensión general del tema."
    )
elif dificultad <= 7:
    st.info(
        "Modo estándar: exige conceptos correctos, relación con el material "
        "y explicación suficiente."
    )
else:
    st.warning(
        "Modo estricto: exige precisión conceptual, claridad, completitud "
        "y relación directa con el material."
    )

mostrar_extraccion = st.checkbox(
    "Mostrar extracción inicial de la imagen",
    value=False,
    help="Muestra lo que Gemini detectó antes de calificar."
)

st.divider()

if st.button("Iniciar Calificación Autónoma", use_container_width=True, type="primary"):
    if not archivos_contexto:
        st.warning("Por favor, sube al menos un archivo de contexto.")
        st.stop()

    if archivo_examen is None:
        st.warning("Por favor, sube la imagen del examen.")
        st.stop()

    rutas_contexto = []
    ruta_img = None

    with st.spinner(
        "Analizando examen, construyendo RAG y generando reporte... Esto puede tomar unos minutos."
    ):
        try:
            for archivo in archivos_contexto:
                extension = Path(archivo.name).suffix.lower()

                with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
                    tmp.write(archivo.getvalue())
                    rutas_contexto.append(tmp.name)

            extension_img = Path(archivo_examen.name).suffix.lower()

            with tempfile.NamedTemporaryFile(delete=False, suffix=extension_img) as tmp_img:
                tmp_img.write(archivo_examen.getvalue())
                ruta_img = tmp_img.name

            if mostrar_extraccion:
                with st.spinner("Extrayendo preguntas y respuestas desde la imagen..."):
                    texto_extraido = extraer_texto_imagen_gemini(ruta_img)

                st.subheader("Extracción inicial de la imagen")
                st.text_area(
                    "Preguntas y respuestas detectadas por Gemini",
                    texto_extraido,
                    height=260
                )

            resultado = calificar_examen_ui(
                ruta_imagen=ruta_img,
                rutas_contexto=rutas_contexto,
                nivel_dificultad=dificultad
            )

            st.success("¡Calificación completada!")

            st.subheader("Reporte de Calificación")
            st.markdown(resultado)

            st.download_button(
                label="Descargar Reporte (TXT)",
                data=resultado,
                file_name="reporte_calificacion.txt",
                mime="text/plain",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Ocurrió un error durante la calificación: {e}")

        finally:
            for ruta in rutas_contexto:
                if ruta and os.path.exists(ruta):
                    os.remove(ruta)

            if ruta_img and os.path.exists(ruta_img):
                os.remove(ruta_img)