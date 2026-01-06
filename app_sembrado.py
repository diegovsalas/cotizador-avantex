import streamlit as st
from PIL import Image, ImageDraw, ImageFont
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
    .metrics-box {
        background-color: #e8fdf5;
        border: 1px solid #6366f1;
        padding: 10px;
        border-radius: 5px;
    }
    iframe {border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Profesional V34")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = ""
if 'sugerencias_puntos' not in st.session_state: st.session_state['sugerencias_puntos'] = ""
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

# --- FUNCION GENERAR PDF (NUEVA) ---
def generar_pdf(imagen_base, puntos, texto_ia, escala_px):
    # 1. Generar la imagen del mapa con matplotlib (igual que antes)
    img_buffer = io.BytesIO()
    fig, ax = plt.subplots(figsize=(10, 10 * imagen_base.height / imagen_base.width))
    ax.imshow(imagen_base)
    ax.axis('off')
    
    for p in puntos:
        c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
        ax.add_patch(c)
        ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
        
    # Testigo en la imagen del PDF
    rect = patches.Rectangle((30, imagen_base.height - 40), escala_px, 5, color='red')
    ax.add_patch(rect)
    ax.text(30, imagen_base.height - 50, '1 Metro', color='red', fontsize=12, backgroundcolor='white')

    plt.savefig(img_buffer, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
    img_buffer.seek(0)

    # 2. Crear el documento PDF con ReportLab
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    estilo_titulo = ParagraphStyle('TituloAromatex', parent=styles['Heading1'], textColor=colors.hexval("#6366f1"), spaceAfter=20)
    estilo_texto = ParagraphStyle('TextoIA', parent=styles['Normal'], fontSize=10, leading=14)

    story = []

    # Título
    story.append(Paragraph("Propuesta de Sembrado Aromatex", estilo_titulo))
    story.append(Spacer(1, 12))

    # Sección de Análisis IA (Si existe)
    if texto_ia:
        story.append(Paragraph("<b>Análisis Estratégico (IA):</b>", styles['Heading3']))
        # Convertimos saltos de línea de texto normal a HTML para el PDF
        texto_formateado = texto_ia.replace("\n", "<br/>")
        story.append(Paragraph(texto_formateado, estilo_texto))
        story.append(Spacer(1, 20))

    # Imagen del Plano
    story.append(Paragraph("<b>Plano de Cobertura:</b>", styles['Heading3']))
    story.append(Spacer(1, 10))
    
    # Ajustar imagen al ancho del PDF
    img_pdf = RLImage(img_buffer)
    available_width = A4[0] - 60 # Ancho A4 menos márgenes
    ratio = available_width / img_pdf.imageWidth
    img_pdf.drawHeight = img_pdf.imageHeight * ratio
    img_pdf.drawWidth = available_width
    story.append(img_pdf)
    
    # Pie de página breve
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Equipos propuestos: {len(puntos)}", styles['Normal']))

    # Construir PDF
    doc.build(story)
    pdf_bytes = pdf_buffer.getvalue()
    img_buffer.close()
    pdf_buffer.close()
    plt.close(fig)
    
    return pdf_bytes

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # --- GESTIÓN INTELIGENTE DE API KEY ---
    api_key = None
    
    # 1. Intentamos leer de los secretos (automático)
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("🔑 API Key cargada automáticamente")
    else:
        # 2. Si no existe, pedimos manual
        with st.expander("🔑 Configuración IA", expanded=True):
            api_key = st.text_input("Google API Key:", type="password")
            st.caption("Consejo: Crea .streamlit/secrets.toml para no escribirla siempre.")

    st.divider()
    
    # --- 2. ESCALA ---
    st.subheader("🔍 Escala")
    col_p1, col_p2, col_p3 = st.columns(3)
    if col_p1.button("🛍️ Retail"):
        st.session_state['scale_px_per_meter'] = 55.0
        st.rerun()
    if col_p2.button("🏢 Ofi"):
        st.session_state['scale_px_per_meter'] = 25.0
        st.rerun()
    if col_p3.button("🏨 Hotel"):
        st.session_state['scale_px_per_meter'] = 15.0
        st.rerun()

    scale = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=1.0)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()
    
    st.caption("Usa la línea roja del mapa como guía de 1 metro.")
    st.divider()

    # --- 3. MODELOS Y SEMBRADO ---
    modo = st.radio("Herramienta:", ["📍 Sembrar Equipos", "📏 Calibrar Escala"], index=0)

    if modo == "📍 Sembrar Equipos":
        tipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
        if "Home" in tipo:
            color = "#2E8B57"
            radio_real = 5.6
        elif "Advance" in tipo:
            color = "#FF8C00"
            radio_real = 9.7
        else:
            color = "#DC143C"
            radio_real = 16.0
        
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        st.caption(f"Radio visual: {radio_px} px")
        
        col1, col2 = st.columns(2)
        if col1.button("↩️ Deshacer"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if col2.button("🗑️ Borrar Todo"):
            st.session_state['puntos'] = []
            st.rerun()

    else: # MODO CALIBRAR
        st.info("Clic A -> Clic B (en una puerta)")
        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            st.write(f"📏 Pixeles: {dist_px:.1f}")
            metros = st.number_input("Metros reales:", value=0.90, step=0.10)
            if st.button("✅ Ajustar"):
                if metros > 0:
                    st.session_state['scale_px_per_meter'] = dist_px / metros
                    st.session_state['calibracion_clicks'] = []
                    st.rerun()
        if st.button("❌ Cancelar"):
            st.session_state['calibracion_clicks'] = []
            st.rerun()

    # --- API KEY ---
    st.divider()
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        with st.expander("🔑 API Key (IA)", expanded=False):
            api_key = st.text_input("Key:", type="password")

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        with st.spinner("Procesando..."):
            st.session_state['base_image'] = process_file(uploaded_file)
            st.session_state['file_id'] = fid
            st.session_state['puntos'] = [] 
            st.session_state['calibracion_clicks'] = []
            st.rerun()

if st.session_state['base_image']:

    # --- ZONA IA ---
    if api_key and modo == "📍 Sembrar Equipos":
        col_btn, col_txt = st.columns([1, 4])
        with col_btn:
            if st.button("✨ Preguntar a Gemini"):
                try:
                    with st.spinner("Analizando..."):
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        prompt = f"""
                        Actúa como experto en Marketing Olfativo.
                        Datos técnicos: Local de {area_total} m² con altura de {altura} m.
                        Analiza el plano visualmente. Dame 3 puntos estratégicos para difusores.
                        FORMATO: "📍 **[Zona]**: [Razón breve]"
                        """
                        response = model.generate_content([prompt, st.session_state['base_image']])
                        st.session_state['sugerencias_puntos'] = response.text
                        st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")
        
        with col_txt:
            if st.session_state['sugerencias_puntos']:
                with st.expander("💡 Sugerencias IA", expanded=True):
                    st.markdown(st.session_state['sugerencias_puntos'])

    # --- CANVAS ---
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # PUNTOS
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=4)
        draw.ellipse((x-6, y-6, x+6, y+6), fill="white", outline="black")
        draw.ellipse((x-3, y-3, x+3, y+3), fill=p['color'])

    # CALIBRACIÓN
    clicks = st.session_state['calibracion_clicks']
    if len(clicks) > 0:
        p1 = clicks[0]
        draw.ellipse((p1['x']-5, p1['y']-5, p1['x']+5, p1['y']+5), fill="blue", outline="white")
        if len(clicks) == 2:
            p2 = clicks[1]
            draw.ellipse((p2['x']-5, p2['y']-5, p2['x']+5, p2['y']+5), fill="blue", outline="white")
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="blue", width=3)

    if modo == "📍 Sembrar Equipos":
        st.write(f"📍 Equipos sembrados: **{len(st.session_state['puntos'])}**")
    else:
        st.info("📏 Calibración: Clic en dos puntos.")

    value = streamlit_image_coordinates(display_img, key="clicker")
    
    if value is not None:
        x, y = value["x"], value["y"]
        
        if modo == "📍 Sembrar Equipos":
            # Usamos el radio calculado dinámicamente arriba
            new_point = {"x": x, "y": y, "color": color, "radio": radio_px}
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != x:
                st.session_state['puntos'].append(new_point)
                st.rerun()
        elif modo == "📏 Calibrar Escala":
            if len(st.session_state['calibracion_clicks']) < 2:
                if not st.session_state['calibracion_clicks'] or st.session_state['calibracion_clicks'][-1]['x'] != x:
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        if st.button("📸 Descargar Propuesta"):
            buf = io.BytesIO()
            fig, ax = plt.subplots(figsize=(12, 12 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
            st.download_button("Bajar Imagen PNG", buf.getvalue(), "sembrado.png", "image/png")