import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai 
from streamlit_image_coordinates import streamlit_image_coordinates
import math

# --- NUEVAS LIBRERÍAS PARA PDF ---
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex + IA", layout="wide", page_icon="🧬")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    iframe {border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Profesional V35")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = "" # Guardaremos el texto aquí
if 'calibracion_clicks' not in st.session_state: st.session_state['calibracion_clicks'] = []

# --- PROCESAMIENTO ---
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
        st.error(f"Error: {e}")
        return None

# --- FUNCION GENERAR PDF ---
def generar_pdf(imagen_base, puntos, texto_ia, escala_px):
    # 1. Crear imagen con matplotlib
    img_buffer = io.BytesIO()
    fig, ax = plt.subplots(figsize=(10, 10 * imagen_base.height / imagen_base.width))
    ax.imshow(imagen_base)
    ax.axis('off')
    
    for p in puntos:
        c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
        ax.add_patch(c)
        ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
        
    # Testigo de escala visual
    rect = patches.Rectangle((30, imagen_base.height - 40), escala_px, 5, color='red')
    ax.add_patch(rect)
    ax.text(30, imagen_base.height - 50, '1 Metro', color='red', fontsize=12, backgroundcolor='white')

    plt.savefig(img_buffer, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
    img_buffer.seek(0)

    # 2. Documento ReportLab
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
    
    # --- INPUTS DE DATOS (IMPORTANTE PARA EVITAR EL ERROR) ---
    st.subheader("📋 Datos del Local")
    area_total = st.number_input("Área (m²):", value=100)
    altura = st.number_input("Altura (m):", value=3.0)
    
    st.divider()

    # --- API KEY ---
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("🔑 API Key cargada")
    else:
        api_key = st.text_input("Google API Key:", type="password")

    st.divider()
    
    # --- ESCALA ---
    st.subheader("🔍 Escala")
    col1, col2 = st.columns(2)
    if col1.button("🛍️ Retail"): st.session_state['scale_px_per_meter'] = 55.0; st.rerun()
    if col2.button("🏢 Ofi"): st.session_state['scale_px_per_meter'] = 25.0; st.rerun()

    scale = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=1.0)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()
    
    st.divider()

    # --- MODOS ---
    modo = st.radio("Herramienta:", ["📍 Sembrar Equipos", "📏 Calibrar Escala"])

    if modo == "📍 Sembrar Equipos":
        tipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
        
        # Definir propiedades según selección
        if "Home" in tipo:
            color, radio_real = "#2E8B57", 5.6
        elif "Advance" in tipo:
            color, radio_real = "#FF8C00", 9.7
        else:
            color, radio_real = "#DC143C", 16.0
        
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        st.caption(f"Radio visual: {radio_px} px")
        
        if st.button("↩️ Deshacer Último"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if st.button("🗑️ Borrar Todo"):
            st.session_state['puntos'] = []
            st.rerun()
    else:
        st.info("Clic A -> Clic B (puerta)")
        if len(st.session_state['calibracion_clicks']) == 2:
            p1, p2 = st.session_state['calibracion_clicks']
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            st.write(f"📏 Pixeles: {dist_px:.1f}")
            metros = st.number_input("Metros reales:", value=0.90)
            if st.button("✅ Ajustar Escala"):
                st.session_state['scale_px_per_meter'] = dist_px / metros
                st.session_state['calibracion_clicks'] = []
                st.rerun()

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = []
        st.session_state['calibracion_clicks'] = []
        st.session_state['analisis_ia'] = "" # Reset análisis al cambiar imagen
        st.rerun()

if st.session_state['base_image']:

    # --- ZONA IA ---
    if api_key and modo == "📍 Sembrar Equipos":
        if st.button("✨ Analizar con Gemini"):
            try:
                with st.spinner("Gemini está pensando..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    # AQUI YA FUNCIONAN LAS VARIABLES PORQUE ESTAN EN EL SIDEBAR
                    prompt = f"""
                    Actúa como experto en Marketing Olfativo.
                    Datos técnicos: Local de {area_total} m² con altura de {altura} m.
                    Analiza el plano visualmente. Dame 3 puntos estratégicos para difusores.
                    Sé breve y profesional.
                    """
                    response = model.generate_content([prompt, st.session_state['base_image']])
                    st.session_state['analisis_ia'] = response.text
                    st.rerun()
            except Exception as e:
                st.error(f"Error IA: {e}")

        if st.session_state['analisis_ia']:
            st.info(st.session_state['analisis_ia'])

    # --- CANVAS ---
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # Dibujar puntos
    for p in st.session_state['puntos']:
        x, y, r, c = p['x'], p['y'], p['radio'], p['color']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=c, width=4)
        draw.ellipse((x-5, y-5, x+5, y+5), fill=c)

    # Dibujar calibración
    clicks = st.session_state['calibracion_clicks']
    for p in clicks:
        draw.ellipse((p['x']-5, p['y']-5, p['x']+5, p['y']+5), fill="blue")
    if len(clicks) == 2:
        draw.line([(clicks[0]['x'], clicks[0]['y']), (clicks[1]['x'], clicks[1]['y'])], fill="blue", width=3)

    # Captura de clics
    value = streamlit_image_coordinates(display_img, key="clicker")
    
    if value:
        x, y = value["x"], value["y"]
        if modo == "📍 Sembrar Equipos":
            # Verificar duplicados por rerun
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != x:
                new_point = {"x": x, "y": y, "color": color, "radio": radio_px}
                st.session_state['puntos'].append(new_point)
                st.rerun()
        elif modo == "📏 Calibrar Escala":
            if len(clicks) < 2:
                 if not clicks or clicks[-1]['x'] != x:
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    # --- DESCARGA PDF ---
    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        st.success(f"Listo para exportar con {len(st.session_state['puntos'])} equipos.")
        
        # Generamos el PDF usando la función nueva
        pdf_bytes = generar_pdf(
            st.session_state['base_image'], 
            st.session_state['puntos'], 
            st.session_state['analisis_ia'],
            st.session_state['scale_px_per_meter']
        )
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📄 Descargar Reporte PDF",
                data=pdf_bytes,
                file_name="propuesta_aromatex.pdf",
                mime="application/pdf"
            )