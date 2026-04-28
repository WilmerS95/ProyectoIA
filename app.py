import streamlit as st
import os
import tempfile
from main import calificar_examen_ui, extraer_texto_imagen

st.set_page_config(page_title="Calificador de Exámenes IA", page_icon="📝", layout="wide")

st.title("Sistema Inteligente Multimodal para la Calificación Autónoma")
st.markdown("Sube el examen del alumno y el material del profesor para iniciar la calificación automatizada.")

# Crear dos columnas para subir archivos
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Material de Clase (Contexto)")
    archivo_contexto = st.file_uploader("Sube el PDF con los apuntes/teoría", type=["pdf"])

with col2:
    st.subheader("2. Examen del Estudiante")
    archivo_examen = st.file_uploader("Sube la foto o escaneo del examen", type=["jpg", "jpeg", "png"])

# Selector de dificultad
st.divider()
st.subheader("3. Configuración de Calificación")
dificultad = st.slider("Nivel de Dificultad (1 = Modo Amigo, 10 = Modo Experto)", min_value=1, max_value=10, value=5)

# Botón para iniciar el proceso
if st.button("Iniciar Calificación Autónoma", use_container_width=True, type="primary"):
    if archivo_contexto is not None and archivo_examen is not None:
        with st.spinner('Analizando examen y generando reporte... Esto puede tomar unos minutos.'):

            # Guardar los archivos temporalmente para que CrewAI pueda leerlos
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
                tmp_pdf.write(archivo_contexto.getvalue())
                ruta_pdf = tmp_pdf.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                tmp_img.write(archivo_examen.getvalue())
                ruta_img = tmp_img.name
                st.text_area("Texto OCR (debug)1", extraer_texto_imagen(ruta_img), height=200)

            try:
                # Llamamos a la lógica de CrewAI
                resultado = calificar_examen_ui(ruta_img, ruta_pdf, dificultad)
                st.text_area("Texto OCR (debug)2", extraer_texto_imagen(ruta_img), height=200)

                st.success("¡Calificación completada!")

                # Mostrar el resultado en pantalla
                st.subheader("Reporte de Calificación")
                if hasattr(resultado, "raw"):
                    st.markdown(resultado.raw)
                else:
                    st.markdown(resultado)
                #st.markdown(resultado) # CrewAI devuelve un objeto, usamos .raw para el texto

                # Opción para descargar el reporte
                st.download_button(
                    label="Descargar Reporte (TXT)",
                    data=resultado,
                    file_name="reporte_calificacion.txt",
                    mime="text/plain"
                )
            except Exception as e:
                st.error(f"Ocurrió un error durante la calificación: {e}")
            finally:
                # Limpiamos los archivos temporales
                os.remove(ruta_pdf)
                os.remove(ruta_img)
    else:
        st.warning("Por favor, sube ambos archivos (Contexto y Examen) antes de iniciar.")