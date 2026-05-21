import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def conectar_db():
    if not DATABASE_URL:
        raise ValueError("Falta DATABASE_URL en el archivo .env")

    return psycopg2.connect(DATABASE_URL)


def guardar_examen_calificado(
    estudiante_nombre=None,
    estudiante_codigo=None,
    curso=None,
    docente=None,
    titulo_examen=None,
    serie_examen=None,
    fecha_examen=None,
    archivo_nombre=None,
    archivo_tipo=None,
    archivo_hash=None,
    nivel_dificultad=None,
    nota_obtenida=None,
    nota_maxima=None,
    nota_escala_100=None,
    porcentaje=None,
    preguntas_buenas=0,
    preguntas_parciales=0,
    preguntas_incorrectas=0,
    total_preguntas=0,
    conclusion_general=None,
    fortalezas=None,
    debilidades=None,
    recomendaciones_estudio=None,
    texto_examen_extraido=None,
    metadatos_extraidos_json=None,
    rubrica_detectada_json=None,
    informe_markdown=None
):
    conn = conectar_db()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO examenes_calificados (
                    estudiante_nombre,
                    estudiante_codigo,
                    curso,
                    docente,
                    titulo_examen,
                    serie_examen,
                    fecha_examen,
                    archivo_nombre,
                    archivo_tipo,
                    archivo_hash,
                    nivel_dificultad,
                    nota_obtenida,
                    nota_maxima,
                    nota_escala_100,
                    porcentaje,
                    preguntas_buenas,
                    preguntas_parciales,
                    preguntas_incorrectas,
                    total_preguntas,
                    conclusion_general,
                    fortalezas,
                    debilidades,
                    recomendaciones_estudio,
                    texto_examen_extraido,
                    metadatos_extraidos_json,
                    rubrica_detectada_json,
                    informe_markdown
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    estudiante_nombre,
                    estudiante_codigo,
                    curso,
                    docente,
                    titulo_examen,
                    serie_examen,
                    fecha_examen,
                    archivo_nombre,
                    archivo_tipo,
                    archivo_hash,
                    nivel_dificultad,
                    nota_obtenida,
                    nota_maxima,
                    nota_escala_100,
                    porcentaje,
                    preguntas_buenas,
                    preguntas_parciales,
                    preguntas_incorrectas,
                    total_preguntas,
                    conclusion_general,
                    fortalezas,
                    debilidades,
                    recomendaciones_estudio,
                    texto_examen_extraido,
                    json.dumps(metadatos_extraidos_json) if metadatos_extraidos_json else None,
                    json.dumps(rubrica_detectada_json) if rubrica_detectada_json else None,
                    informe_markdown
                )
            )

            examen_id = cur.fetchone()[0]
            conn.commit()
            return examen_id

    finally:
        conn.close()


def listar_historial():
    conn = conectar_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    id,
                    estudiante_nombre,
                    curso,
                    titulo_examen,
                    serie_examen,
                    nivel_dificultad,
                    nota_obtenida,
                    nota_maxima,
                    nota_escala_100,
                    preguntas_buenas,
                    preguntas_parciales,
                    preguntas_incorrectas,
                    total_preguntas,
                    creado_en
                FROM examenes_calificados
                ORDER BY creado_en DESC;
                """
            )
            return cur.fetchall()

    finally:
        conn.close()


def obtener_examen_por_id(examen_id):
    conn = conectar_db()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM examenes_calificados
                WHERE id = %s;
                """,
                (examen_id,)
            )
            return cur.fetchone()

    finally:
        conn.close()