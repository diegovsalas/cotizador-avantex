import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai
from streamlit_image_coordinates import streamlit_image_coordinates
import math

# --- LIBRERÍAS REPORTLAB (PDF) ---
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# =========================================================
# CATÁLOGO OFICIAL AROMATEX
# Fuente: https://aromatex.mx/collections/difusores-inteligentes
# NOTA: Las coberturas son "máximas ideales" del fabricante
# asumiendo altura estándar 3m y espacio abierto.
# Ajustar por "factor_espacio" cuando haya obstrucciones.
# =========================================================
CATALOGO = {
    "Home Pro": {
        "cobertura_m2": 100,
        "color": "#3B82F6",       # Azul
        "capacidad_ml": 250,
        "descripcion": "Ideal para baños, oficinas chicas, recepciones",
    },
    "Advance Pro": {
        "cobertura_m2": 300,
        "color": "#10B981",       # Verde esmeralda (match QBR Aromatex)
        "capacidad_ml": 800,
        "descripcion": "Retail mediano, showrooms, pasillos comerciales",
    },
    "Plus Pro": {
        "cobertura_m2": 500,
        "color": "#F59E0B",       # Ámbar
        "capacidad_ml": 800,
        "descripcion": "Salones amplios, grandes áreas comerciales",
    },
    "Extreme Pro": {
        "cobertura_m2": 800,      # [CONFIRMAR con ficha técnica interna]
        "color": "#EF4444",       # Rojo
        "capacidad_ml": 1000,
        "descripcion": "Centros comerciales, lobbies, auditorios",
    },
}

# Factor de ajuste por tipo de espacio
# Multiplica la cobertura base. >1 = rinde más, <1 = rinde menos
FACTORES_ESPACIO = {
    "Retail abierto (planta libre)": 1.00,
    "Oficina con divisiones": 0.75,
    "Restaurante (aromas de cocina)": 0.60,
    "Hotel / Lobby": 0.90,
    "Espacio con HVAC (ducto)": 1.15,
    "Techos altos (>3.5m)": 0.70,
}

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🧬")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .stButton>button {width: 100%;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Profesional V42")
st.caption("Catálogo sincronizado con aromatex.mx · Cobertura por tipo de espacio")

# --- ESTADO (SESSION STATE) ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = ""
if 'calibracion_clicks' not in st.session_state: st.session_state['calibracion_clicks'] = []
if 'calibracion_ia' not in st.session_state: st.session_state['calibracion_ia'] = None

# --- FUNCIÓN PROCESAR IMAGEN/PDF ---
def process_file(uploaded_file):
    try:
        image = None
        uploaded_file.seek(0)
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

        target_width = 1000
        if image.width > target_width:
            ratio = target_width / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((target_width, h), Image.Resampling.LANCZOS)
        return image
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

# --- FUNCIÓN: Calcula cobertura ajustada de un modelo ---
def cobertura_ajustada(modelo, factor_espacio):
    """Retorna cobertura real en m² considerando el tipo de espacio."""
    base = CATALOGO[modelo]["cobertura_m2"]
    return base * factor_espacio

# --- FUNCIÓN: Calcula radio en px ---
def calcular_radio_px(cobertura_m2, scale_px_per_m):
    """Radio de un círculo equivalente a la cobertura en m²."""
    radio_m = math.sqrt(cobertura_m2 / math.pi)
    return int(radio_m * scale_px_per_m)


# --- FUNCIÓN: Auto-calibración con Gemini Vision ---
def auto_calibrar_con_ia(imagen, api_key):
    """
    Pide a Gemini que detecte un elemento de escala en el plano.
    Retorna dict con puntos + medida real, o None si falla.

    Prioriza cotas impresas > puertas estándar > estimación visual.
    """
    import json

    # Reducir imagen para enviar a API (mismo criterio que análisis)
    w, h = imagen.size
    max_dim = 1024
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img_para_api = imagen.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        escala_reduccion = ratio
    else:
        img_para_api = imagen
        escala_reduccion = 1.0

    prompt = """Eres un analista de planos arquitectónicos. Tu tarea: detectar la escala del plano.

REGLAS ESTRICTAS:
1. Busca PRIMERO cotas dimensionales impresas (números con líneas de dimensión, ej. "5.20", "3.00 M").
2. Si NO hay cotas, busca una PUERTA completa (ancho estándar en México: 0.90 m).
3. Como último recurso, estima dimensiones del espacio total basándote en elementos típicos.

COORDENADAS:
- Las coordenadas (x, y) están en pixeles.
- El origen (0, 0) es la ESQUINA SUPERIOR IZQUIERDA.
- x crece hacia la DERECHA, y crece hacia ABAJO.
- Dimensiones de la imagen que analizas: ancho y alto se te indican abajo.

Devuelve SOLO JSON con este formato exacto:
{
  "metodo_usado": "cota_impresa" | "puerta_estandar" | "estimacion_visual",
  "confianza": "alta" | "media" | "baja",
  "punto_1": {"x": <int>, "y": <int>},
  "punto_2": {"x": <int>, "y": <int>},
  "distancia_metros": <float>,
  "descripcion": "<breve explicación de qué detectaste>"
}

Los dos puntos deben ser los EXTREMOS de lo que mediste (inicio y fin de la cota o ancho de la puerta)."""

    prompt += f"\n\nDimensiones de la imagen: ancho={img_para_api.width}px, alto={img_para_api.height}px."

    MODELOS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite']

    for modelo_id in MODELOS:
        try:
            genai.configure(api_key=api_key)
            # response_mime_type fuerza respuesta JSON
            model = genai.GenerativeModel(
                modelo_id,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(
                [prompt, img_para_api],
                request_options={"timeout": 60}
            )
            # Parsear JSON
            data = json.loads(response.text)

            # Validar campos requeridos
            required = ["metodo_usado", "confianza", "punto_1", "punto_2", "distancia_metros"]
            if not all(k in data for k in required):
                continue

            # Convertir coordenadas al tamaño original si hubo reducción
            if escala_reduccion != 1.0:
                data["punto_1"]["x"] = int(data["punto_1"]["x"] / escala_reduccion)
                data["punto_1"]["y"] = int(data["punto_1"]["y"] / escala_reduccion)
                data["punto_2"]["x"] = int(data["punto_2"]["x"] / escala_reduccion)
                data["punto_2"]["y"] = int(data["punto_2"]["y"] / escala_reduccion)

            # Calcular escala px/m
            dx = data["punto_2"]["x"] - data["punto_1"]["x"]
            dy = data["punto_2"]["y"] - data["punto_1"]["y"]
            dist_px = math.sqrt(dx**2 + dy**2)

            if data["distancia_metros"] <= 0 or dist_px <= 0:
                continue

            data["escala_px_per_m"] = dist_px / data["distancia_metros"]
            data["dist_px"] = dist_px
            data["modelo_usado"] = modelo_id
            return data

        except json.JSONDecodeError:
            continue
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                continue
            else:
                return {"error": str(e)}

    return None


# --- FUNCIÓN GENERAR PDF ---
def generar_pdf(imagen_base, puntos, texto_ia, escala_px, area_total, factor_espacio, resumen):
    img_buffer = io.BytesIO()
    fig, ax = plt.subplots(figsize=(10, 10 * imagen_base.height / imagen_base.width))
    ax.imshow(imagen_base)
    ax.axis('off')

    for p in puntos:
        c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
        ax.add_patch(c)
        ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))

    rect = patches.Rectangle((30, imagen_base.height - 40), escala_px, 5, color='red')
    ax.add_patch(rect)
    ax.text(30, imagen_base.height - 50, '1 Metro', color='red', fontsize=12, backgroundcolor='white')

    plt.savefig(img_buffer, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
    img_buffer.seek(0)

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle('TituloAromatex', parent=styles['Heading1'], textColor=colors.HexColor("#10B981"), spaceAfter=20)
    estilo_texto = ParagraphStyle('TextoIA', parent=styles['Normal'], fontSize=10, leading=14)

    story = []
    story.append(Paragraph("Propuesta de Sembrado Aromatex", estilo_titulo))
    story.append(Paragraph(f"<b>Área declarada:</b> {area_total} m² · <b>Tipo:</b> {factor_espacio}", estilo_texto))
    story.append(Spacer(1, 12))

    if texto_ia:
        story.append(Paragraph("<b>Análisis Estratégico (IA):</b>", styles['Heading3']))
        texto_formateado = texto_ia.replace("\n", "<br/>")
        story.append(Paragraph(texto_formateado, estilo_texto))
        story.append(Spacer(1, 20))

    # Tabla resumen de equipos
    if resumen:
        story.append(Paragraph("<b>Resumen de Equipos:</b>", styles['Heading3']))
        data = [["Modelo", "Cantidad", "Cobertura c/u", "Cobertura total"]]
        for modelo, info in resumen.items():
            data.append([modelo, str(info["cantidad"]), f"{info['cobertura_unit']:.0f} m²", f"{info['cobertura_total']:.0f} m²"])
        t = Table(data, colWidths=[120, 60, 90, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#10B981")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Plano de Cobertura:</b>", styles['Heading3']))
    story.append(Spacer(1, 10))

    img_pdf = RLImage(img_buffer)
    available_width = A4[0] - 60
    ratio = available_width / img_pdf.imageWidth
    img_pdf.drawHeight = img_pdf.imageHeight * ratio
    img_pdf.drawWidth = available_width
    story.append(img_pdf)

    doc.build(story)
    pdf_bytes = pdf_buffer.getvalue()
    img_buffer.close()
    pdf_buffer.close()
    plt.close(fig)
    return pdf_bytes

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")

    st.subheader("📋 Datos del Local")
    area_total = st.number_input("Área declarada (m²):", value=100, min_value=1)
    altura = st.number_input("Altura (m):", value=3.00, step=0.10, min_value=2.0)

    tipo_espacio = st.selectbox("Tipo de espacio:", list(FACTORES_ESPACIO.keys()))
    factor = FACTORES_ESPACIO[tipo_espacio]

    if altura > 3.5:
        factor = min(factor, FACTORES_ESPACIO["Techos altos (>3.5m)"])
        st.warning(f"⚠️ Techo alto detectado. Factor ajustado: {factor:.2f}")
    else:
        st.caption(f"📊 Factor aplicado: **{factor:.2f}**")

    st.divider()

    # --- API KEY ---
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("🔑 API Key (Secrets)")
    else:
        api_key = st.text_input("Google API Key:", type="password")
        if not api_key:
            st.warning("⚠️ Ingresa tu API Key para usar la IA")

    st.divider()

    st.subheader("🔍 Escala")
    col1, col2 = st.columns(2)
    if col1.button("🛍️ Retail"): st.session_state['scale_px_per_meter'] = 55.0; st.rerun()
    if col2.button("🏢 Ofi"): st.session_state['scale_px_per_meter'] = 25.0; st.rerun()

    scale = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=1.0)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()

    st.divider()

    modo = st.radio("Herramienta:", ["📍 Sembrar Equipos", "📏 Calibrar Escala"])

    if modo == "📍 Sembrar Equipos":
        tipo = st.selectbox("Modelo", list(CATALOGO.keys()))
        info_modelo = CATALOGO[tipo]

        cobertura_m2_real = cobertura_ajustada(tipo, factor)
        color = info_modelo["color"]
        radio_px = calcular_radio_px(cobertura_m2_real, st.session_state['scale_px_per_meter'])

        st.caption(f"📐 Cobertura oficial: **{info_modelo['cobertura_m2']} m²**")
        st.caption(f"📏 Cobertura ajustada: **{cobertura_m2_real:.0f} m²**")
        st.caption(f"💧 Capacidad: **{info_modelo['capacidad_ml']} ml**")
        st.info(info_modelo["descripcion"])

        c1, c2 = st.columns(2)
        if c1.button("↩️ Deshacer"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if c2.button("🗑️ Borrar"):
            st.session_state['puntos'] = []
            st.rerun()
    else:
        st.subheader("🤖 Auto-calibración con IA")

        if api_key and st.session_state['base_image'] is not None:
            if st.button("✨ Detectar escala automáticamente"):
                with st.status("🔍 Analizando plano...", expanded=True) as status:
                    st.write("📡 Pidiendo a Gemini que detecte escala...")
                    resultado = auto_calibrar_con_ia(
                        st.session_state['base_image'],
                        api_key
                    )
                    if resultado and "error" not in resultado:
                        st.session_state['calibracion_ia'] = resultado
                        st.write(f"✅ Detectado: {resultado['descripcion']}")
                        status.update(label="✅ Escala detectada", state="complete")
                    elif resultado and "error" in resultado:
                        st.write(f"❌ Error: {resultado['error'][:150]}")
                        status.update(label="❌ Falló detección", state="error")
                    else:
                        st.write("❌ No se pudo detectar escala en el plano")
                        status.update(label="❌ Falló detección", state="error")
                st.rerun()
        elif not api_key:
            st.caption("⚠️ Requiere API Key de Google arriba")

        # Mostrar resultado de auto-calibración IA
        if st.session_state['calibracion_ia']:
            cal = st.session_state['calibracion_ia']
            confianza_emoji = {"alta": "🟢", "media": "🟡", "baja": "🔴"}.get(cal['confianza'], "⚪")

            with st.container(border=True):
                st.markdown(f"**{confianza_emoji} Confianza: {cal['confianza']}**")
                st.caption(f"Método: `{cal['metodo_usado']}`")
                st.caption(f"📐 {cal['descripcion']}")
                st.caption(f"📏 Distancia detectada: {cal['distancia_metros']} m = {cal['dist_px']:.0f} px")
                st.caption(f"📊 Escala calculada: **{cal['escala_px_per_m']:.1f} px/m**")

                c1, c2 = st.columns(2)
                if c1.button("✅ Aplicar"):
                    st.session_state['scale_px_per_meter'] = cal['escala_px_per_m']
                    st.session_state['calibracion_ia'] = None
                    st.rerun()
                if c2.button("❌ Descartar"):
                    st.session_state['calibracion_ia'] = None
                    st.rerun()

        st.divider()
        st.subheader("📏 Calibración manual")
        st.caption("Clic en 2 puntos de referencia conocida.")

        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            st.write(f"📏 Pixeles: {dist_px:.1f}")
            metros = st.number_input("Metros reales:", value=0.90)
            if st.button("✅ Aplicar Escala Manual"):
                if metros > 0:
                    st.session_state['scale_px_per_meter'] = dist_px / metros
                    st.session_state['calibracion_clicks'] = []
                    st.rerun()

# --- ÁREA PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"], key="loader")

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = []
        st.session_state['calibracion_clicks'] = []
        st.session_state['calibracion_ia'] = None
        st.session_state['analisis_ia'] = ""
        st.rerun()

# --- LÓGICA DE DIBUJO ---
if st.session_state['base_image']:

    # 1. SECCIÓN IA
    if api_key and modo == "📍 Sembrar Equipos":
        col_ia_btn, col_ia_txt = st.columns([1, 3])
        with col_ia_btn:
            if st.button("✨ Analizar (Gemini)"):
                # Cascada de modelos: intenta del más capaz al más ligero
                MODELOS_CASCADA = [
                    'gemini-2.5-flash',         # 10 RPM / 500 RPD free tier
                    'gemini-2.5-flash-lite',    # 15 RPM / 1000 RPD free tier
                ]

                prompt = f"""
                Eres experto en Marketing Olfativo de Aromatex.
                Local de {area_total} m², altura {altura}m, tipo: {tipo_espacio}.
                Catálogo disponible:
                - Home Pro (100 m²)
                - Advance Pro (300 m²)
                - Plus Pro (500 m²)
                - Extreme Pro (800 m²)
                Analiza la imagen. Recomienda qué modelo y cuántos equipos usar,
                y 3 zonas estratégicas para colocarlos.
                Responde en español, breve, con bullet points.
                """

                # Usar st.status en vez de spinner: muestra progreso paso a paso
                with st.status("🔍 Analizando plano con IA...", expanded=True) as status:
                    respuesta_obtenida = False
                    errores_detalle = []

                    # Paso 1: Optimizar imagen (reducir tamaño = menos tokens = más rápido)
                    st.write("📐 Optimizando imagen para la API...")
                    img_original = st.session_state['base_image']
                    w, h = img_original.size
                    st.write(f"   Tamaño original: {w}×{h} px")

                    # Gemini funciona bien con imágenes de ~1024px máximo
                    max_dim = 1024
                    if max(w, h) > max_dim:
                        ratio = max_dim / max(w, h)
                        new_size = (int(w * ratio), int(h * ratio))
                        img_para_api = img_original.resize(new_size, Image.Resampling.LANCZOS)
                        st.write(f"   Redimensionada a: {new_size[0]}×{new_size[1]} px")
                    else:
                        img_para_api = img_original
                        st.write("   No requiere redimensión")

                    # Paso 2: Configurar API
                    st.write("🔐 Configurando credenciales...")
                    try:
                        genai.configure(api_key=api_key)
                        st.write("   ✅ API key aceptada")
                    except Exception as e:
                        st.write(f"   ❌ Error de configuración: {e}")
                        status.update(label="❌ Falló configuración", state="error")
                        st.stop()

                    # Paso 3: Intentar cascada de modelos
                    for modelo_id in MODELOS_CASCADA:
                        st.write(f"📡 Probando **{modelo_id}**...")
                        try:
                            model = genai.GenerativeModel(modelo_id)
                            st.write(f"   📤 Enviando solicitud (timeout: 60s)...")

                            # Llamada con timeout explícito
                            response = model.generate_content(
                                [prompt, img_para_api],
                                request_options={"timeout": 60}
                            )

                            # Validar que la respuesta tenga contenido
                            if response and response.text:
                                st.session_state['analisis_ia'] = response.text
                                st.write(f"   ✅ Respuesta recibida ({len(response.text)} caracteres)")
                                status.update(
                                    label=f"✅ Análisis completado con {modelo_id}",
                                    state="complete",
                                    expanded=False
                                )
                                respuesta_obtenida = True
                                break
                            else:
                                st.write("   ⚠️ Respuesta vacía (posible filtro de seguridad)")
                                errores_detalle.append((modelo_id, "Respuesta vacía"))
                                continue

                        except Exception as e:
                            error_str = str(e)
                            errores_detalle.append((modelo_id, error_str))
                            if "429" in error_str or "quota" in error_str.lower():
                                st.write(f"   ⚠️ Sin cuota. Probando siguiente modelo...")
                                continue
                            elif "timeout" in error_str.lower() or "deadline" in error_str.lower():
                                st.write(f"   ⏱️ Timeout — la API tardó más de 60s")
                                continue
                            else:
                                st.write(f"   ❌ Error: {error_str[:200]}")
                                break

                    if not respuesta_obtenida:
                        status.update(label="❌ Ningún modelo respondió", state="error")

                # Fuera del status: mostrar resultado o error
                if respuesta_obtenida:
                    st.rerun()
                else:
                    st.error("❌ No se pudo generar el análisis.")
                    with st.expander("🔍 Ver errores técnicos"):
                        for modelo_id, err in errores_detalle:
                            st.markdown(f"**{modelo_id}:**")
                            st.code(err, language=None)

                    st.info(
                        "💡 **Pasos a probar:**\n"
                        "1. Crear API key nueva en https://aistudio.google.com/app/apikey\n"
                        "2. Verificar que el plano no sea demasiado complejo\n"
                        "3. Activar Tier 1 (billing) en https://ai.google.dev"
                    )

        with col_ia_txt:
            if st.session_state['analisis_ia']:
                st.info(st.session_state['analisis_ia'])

    st.divider()

    # 2. SECCIÓN MAPA
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")

    for p in st.session_state['puntos']:
        x, y, r, c = p['x'], p['y'], p['radio'], p['color']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=c, width=4)
        draw.ellipse((x-5, y-5, x+5, y+5), fill=c, outline="white")

    clicks = st.session_state['calibracion_clicks']
    for p in clicks:
        draw.ellipse((p['x']-5, p['y']-5, p['x']+5, p['y']+5), fill="blue")
    if len(clicks) == 2:
        draw.line([(clicks[0]['x'], clicks[0]['y']), (clicks[1]['x'], clicks[1]['y'])], fill="blue", width=3)

    # Dibujar puntos detectados por IA (si hay)
    if st.session_state['calibracion_ia']:
        cal = st.session_state['calibracion_ia']
        p1, p2 = cal['punto_1'], cal['punto_2']
        # Línea magenta entre los dos puntos detectados
        draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="magenta", width=4)
        # Círculos en los extremos
        for p in [p1, p2]:
            draw.ellipse((p['x']-8, p['y']-8, p['x']+8, p['y']+8), outline="magenta", width=3, fill="white")
        # Etiqueta con la medida
        mid_x = (p1['x'] + p2['x']) // 2
        mid_y = (p1['y'] + p2['y']) // 2
        draw.text((mid_x + 10, mid_y - 10), f"{cal['distancia_metros']} m", fill="magenta")

    value = streamlit_image_coordinates(display_img, key="mapa_interactivo")

    if value:
        x, y = value["x"], value["y"]
        if modo == "📍 Sembrar Equipos":
            same_point = False
            if st.session_state['puntos']:
                last = st.session_state['puntos'][-1]
                if abs(last['x'] - x) < 5 and abs(last['y'] - y) < 5:
                    same_point = True
            if not same_point:
                st.session_state['puntos'].append({
                    "x": x, "y": y,
                    "color": color,
                    "radio": radio_px,
                    "modelo": tipo,
                    "cobertura_m2": cobertura_m2_real,
                })
                st.rerun()
        elif modo == "📏 Calibrar Escala":
            if len(clicks) < 2:
                if not clicks or (abs(clicks[-1]['x'] - x) > 5):
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    # 3. SECCIÓN VALIDADOR DE COHERENCIA + RESUMEN
    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()

        # Construir resumen por modelo
        resumen = {}
        for p in st.session_state['puntos']:
            m = p.get("modelo", "Desconocido")
            cov = p.get("cobertura_m2", 0)
            if m not in resumen:
                resumen[m] = {"cantidad": 0, "cobertura_unit": cov, "cobertura_total": 0}
            resumen[m]["cantidad"] += 1
            resumen[m]["cobertura_total"] += cov

        cobertura_total_sembrada = sum(r["cobertura_total"] for r in resumen.values())
        pct_cobertura = (cobertura_total_sembrada / area_total * 100) if area_total else 0

        st.subheader("📊 Validador de Coherencia")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Área declarada", f"{area_total} m²")
        col_b.metric("Cobertura sembrada", f"{cobertura_total_sembrada:.0f} m²")
        col_c.metric("% Cobertura", f"{pct_cobertura:.0f}%")

        # Alertas inteligentes
        if pct_cobertura < 80:
            st.warning(f"⚠️ **Sub-dimensionado**: faltan ~{area_total - cobertura_total_sembrada:.0f} m² por cubrir.")
        elif pct_cobertura > 150:
            st.error(f"🚨 **Sobre-dimensionado**: estás {pct_cobertura - 100:.0f}% arriba del área. Probable desperdicio.")
        elif 80 <= pct_cobertura <= 120:
            st.success(f"✅ **Cobertura óptima** ({pct_cobertura:.0f}% del área declarada).")
        else:
            st.info(f"ℹ️ Cobertura al {pct_cobertura:.0f}% — aceptable con margen.")

        # Tabla resumen
        st.subheader("🧾 Resumen de Equipos")
        tabla_md = "| Modelo | Cantidad | Cobertura c/u | Cobertura total |\n|---|---|---|---|\n"
        for modelo, info in resumen.items():
            tabla_md += f"| {modelo} | {info['cantidad']} | {info['cobertura_unit']:.0f} m² | {info['cobertura_total']:.0f} m² |\n"
        st.markdown(tabla_md)

        # Sección de descarga
        col_res, col_down = st.columns([2, 1])
        with col_res:
            st.success(f"✅ Proyecto listo: {len(st.session_state['puntos'])} equipos.")
        with col_down:
            pdf_data = generar_pdf(
                st.session_state['base_image'],
                st.session_state['puntos'],
                st.session_state['analisis_ia'],
                st.session_state['scale_px_per_meter'],
                area_total,
                tipo_espacio,
                resumen,
            )
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf_data,
                file_name="propuesta_aromatex.pdf",
                mime="application/pdf"
            )
