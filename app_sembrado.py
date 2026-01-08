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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🧬")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .stButton>button {width: 100%;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Profesional V39")

# --- ESTADO (SESSION STATE) ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = "" 
if 'calibracion_clicks' not in st.session_state: st.session_state['calibracion_clicks'] = []

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

        # Convertir a RGB seguro
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

        # Redimensionar si es gigante (optimización)
        target_width = 1000
        if image.width > target_width:
            ratio = target_width / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((target_width, h), Image.Resampling.LANCZOS)
        return image
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

# --- FUNCIÓN GENERAR PDF ---
def generar_pdf(imagen_base, puntos, texto_ia, escala_px):
    # 1. Matplotlib para el plano
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

    # 2. ReportLab para el PDF final
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle('TituloAromatex', parent=styles['Heading1'], textColor=colors.hexval("#6366f1"), spaceAfter=20)
    estilo_texto = ParagraphStyle('TextoIA', parent=styles['Normal'], fontSize=10, leading=14)

    story = []
    story.append(Paragraph("Propuesta de Sembrado Aromatex", estilo_titulo))
    story.append(Spacer(1, 12))

    if texto_ia:
        story.append(Paragraph("<b>Análisis Estratégico (IA):</b>", styles['Heading3']))
        texto_formateado = texto_ia.replace("\n", "<br/>")
        story.append(Paragraph(texto_formateado, estilo_texto))
        story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Plano de Cobertura:</b>", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    img_pdf = RLImage(img_buffer)
    available_width = A4[0] - 60
    ratio = available_width / img_pdf.imageWidth
    img_pdf.drawHeight = img_pdf.imageHeight * ratio
    img_pdf.drawWidth = available_width
    story.append(img_pdf)
    
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Equipos propuestos: {len(puntos)}", styles['Normal']))

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
    area_total = st.number_input("Área (m²):", value=100)
    altura = st.number_input("Altura (m):", value=3.0)
    st.divider()

    # --- API KEY (MANEJO DE ERRORES) ---
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
        tipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
        
        if "Home" in tipo:
            color, radio_real = "#2E8B57", 5.6
        elif "Advance" in tipo:
            color, radio_real = "#FF8C00", 9.7
        else:
            color, radio_real = "#DC143C", 16.0
        
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        st.caption(f"Radio visual: {radio_px} px")
        
        c1, c2 = st.columns(2)
        if c1.button("↩️ Deshacer"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if c2.button("🗑️ Borrar"):
            st.session_state['puntos'] = []
            st.rerun()
    else:
        st.info("Clic en 2 puntos de referencia (ej: puerta).")
        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            st.write(f"📏 Pixeles: {dist_px:.1f}")
            metros = st.number_input("Metros reales:", value=0.90)
            if st.button("✅ Aplicar Escala"):
                if metros > 0:
                    st.session_state['scale_px_per_meter'] = dist_px / metros
                    st.session_state['calibracion_clicks'] = []
                    st.rerun()

# --- ÁREA PRINCIPAL ---
# Usamos key="loader" para que no se resetee el input al hacer rerun
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"], key="loader")

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = []
        st.session_state['calibracion_clicks'] = []
        st.session_state['analisis_ia'] = "" 
        st.rerun()

# --- LÓGICA DE DIBUJO Y RENDERIZADO (SEPARADA) ---
if st.session_state['base_image']:

    # 1. SECCIÓN IA (Arriba del mapa)
    if api_key and modo == "📍 Sembrar Equipos":
        col_ia_btn, col_ia_txt = st.columns([1, 3])
        
        with col_ia_btn:
            if st.button("✨ Analizar (Gemini)"):
                try:
                    with st.spinner("Pensando..."):
                        genai.configure(api_key=api_key)
                        
                        # Intento robusto de selección de modelo
                        try:
                            model = genai.GenerativeModel('gemini-2.0-flash')
                        except:
                            try:
                                model = genai.GenerativeModel('gemini-1.5-flash')
                            except:
                                model = genai.GenerativeModel('gemini-pro-vision')

                        prompt = f"""
                        Eres experto en Marketing Olfativo. Local de {area_total} m2, altura {altura}m.
                        Analiza la imagen. Recomienda 3 zonas estratégicas para difusores de aroma.
                        Responde en español, breve y con bullet points.
                        """
                        response = model.generate_content([prompt, st.session_state['base_image']])
                        st.session_state['analisis_ia'] = response.text
                        st.rerun() # Recarga para mostrar resultado
                        
                except Exception as e:
                    st.error(f"Error IA: {str(e)}")
                    # Importante: No hacemos rerun si hay error para poder leerlo
        
        with col_ia_txt:
            if st.session_state['analisis_ia']:
                st.info(st.session_state['analisis_ia'])

    st.divider()

    # 2. SECCIÓN MAPA (Siempre se ejecuta si existe la imagen)
    # Crear copia para dibujar (no modificamos la original)
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # Dibujar puntos existentes
    for p in st.session_state['puntos']:
        x, y, r, c = p['x'], p['y'], p['radio'], p['color']
        # Radio de cobertura
        draw.ellipse((x-r, y-r, x+r, y+r), outline=c, width=4)
        # Punto central
        draw.ellipse((x-5, y-5, x+5, y+5), fill=c, outline="white")

    # Dibujar línea de calibración
    clicks = st.session_state['calibracion_clicks']
    for p in clicks:
        draw.ellipse((p['x']-5, p['y']-5, p['x']+5, p['y']+5), fill="blue")
    if len(clicks) == 2:
        draw.line([(clicks[0]['x'], clicks[0]['y']), (clicks[1]['x'], clicks[1]['y'])], fill="blue", width=3)

    # RENDERIZAR IMAGEN CLICKEABLE
    # Esta función es la que muestra el mapa. Si el script fallara antes, esto no saldría.
    value = streamlit_image_coordinates(display_img, key="mapa_interactivo")
    
    # Lógica de clicks
    if value:
        x, y = value["x"], value["y"]
        
        if modo == "📍 Sembrar Equipos":
            # Evitar doble click fantasma verificando el último punto
            same_point = False
            if st.session_state['puntos']:
                last = st.session_state['puntos'][-1]
                if abs(last['x'] - x) < 5 and abs(last['y'] - y) < 5:
                    same_point = True
            
            if not same_point:
                st.session_state['puntos'].append({
                    "x": x, "y": y, 
                    "color": color, 
                    "radio": radio_px
                })
                st.rerun()

        elif modo == "📏 Calibrar Escala":
            if len(clicks) < 2:
                # Evitar repetidos
                if not clicks or (abs(clicks[-1]['x'] - x) > 5):
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    # 3. SECCIÓN DESCARGA (Solo si hay equipos)
    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        col_res, col_down = st.columns([2, 1])
        with col_res:
            st.success(f"✅ Proyecto listo: {len(st.session_state['puntos'])} equipos sembrados.")
        with col_down:
            pdf_data = generar_pdf(
                st.session_state['base_image'],
                st.session_state['puntos'],
                st.session_state['analisis_ia'],
                st.session_state['scale_px_per_meter']
            )
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf_data,
                file_name="propuesta_aromatex.pdf",
                mime="application/pdf"
            )
