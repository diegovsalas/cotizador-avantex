import streamlit as st
from PIL import Image
import io
import base64
import uuid
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import fitz  # PyMuPDF

# --- 1. PARCHE DE COMPATIBILIDAD (CRÍTICO) ---
# Esto arregla el conflicto entre Streamlit 1.38+ y el Canvas
import streamlit.elements.image as st_image

def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None):
    """
    Función 'parche' que sustituye a la original de Streamlit eliminada.
    Convierte la imagen a Base64 para que el canvas la pueda leer.
    """
    buffered = io.BytesIO()
    # Guardamos siempre como PNG para preservar calidad y transparencia
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

# Inyectamos nuestra función en el módulo de Streamlit
st_image.image_to_url = custom_image_to_url

# Ahora sí importamos el canvas (usará nuestra función inyectada)
from streamlit_drawable_canvas import st_canvas


# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    /* Borde sutil para ver el límite del editor */
    iframe {border: 1px solid #444;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V21 (Sistema Parcheado)")

# --- 3. ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- 4. PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        # Reiniciar puntero
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        pil_image = None
        
        # A) PDF
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pil_image = Image.open(io.BytesIO(pix.tobytes("png")))
        # B) Imagen
        else:
            pil_image = Image.open(io.BytesIO(file_bytes))
            
        # Normalización (Fondo Blanco + RGB)
        if pil_image.mode != "RGB":
            bg = Image.new("RGB", pil_image.size, (255, 255, 255))
            if pil_image.mode in ('RGBA', 'LA') or (pil_image.mode == 'P' and 'transparency' in pil_image.info):
                bg.paste(pil_image, mask=pil_image.convert("RGBA").split()[3])
            else:
                bg.paste(pil_image)
            pil_image = bg
        else:
            pil_image = pil_image.convert("RGB")

        # Redimensionado (Max 1000px)
        MAX_WIDTH = 1000
        if pil_image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(pil_image.width)
            h = int(float(pil_image.height) * float(ratio))
            pil_image = pil_image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        st.session_state['bg_image'] = pil_image
        st.session_state['canvas_key'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    tipo_equipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
    if "Home" in tipo_equipo:
        color = "#2E8B57"
        radio_real = 5.6
    elif "Advance" in tipo_equipo:
        color = "#FF8C00"
        radio_real = 9.7
    else:
        color = "#DC143C"
        radio_real = 16.0
        
    st.divider()
    modo = st.radio("Herramienta", ["📏 Calibrar Escala", "📍 Sembrar Equipos"])
    
    scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()
        
    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio visual: {radio_px} px")

    if st.button("🗑️ Reiniciar"):
        st.session_state['bg_image'] = None
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

# --- 6. APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_id:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_id
        st.rerun()

if st.session_state['bg_image']:
    img_pil = st.session_state['bg_image']
    
    st.write("### Editor de Sembrado")
    
    # IMPORTANTE: Ahora pasamos 'img_pil' (Objeto Imagen) normalmente.
    # El 'parche' de arriba se encargará de que funcione.
    canvas_result = st_canvas(
        fill_color=color + "55",
        stroke_width=2,
        stroke_color=color,
        background_image=img_pil, 
        update_streamlit=True,
        height=img_pil.height,
        width=img_pil.width,
        drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
        point_display_radius=radio_px,
        display_toolbar=True,
        key=st.session_state['canvas_key']
    )
    
    # Lógica de Herramientas
    if canvas_result.json_data and "objects" in canvas_result.json_data:
        objects = canvas_result.json_data["objects"]
        if len(objects) > 0:
            if modo == "📏 Calibrar Escala":
                try:
                    obj = objects[-1]
                    dist = math.sqrt((obj["width"]*obj["scaleX"])**2 + (obj["height"]*obj["scaleY"])**2)
                    st.info(f"Distancia: {dist:.1f} px")
                    m = st.number_input("Metros reales:", 1.0)
                    if st.button("Guardar Escala"):
                        st.session_state['scale_px_per_meter'] = dist / m
                        st.rerun()
                except: pass
            
            elif modo == "📍 Sembrar Equipos":
                st.metric("Equipos", len(objects))
                if st.button("Descargar Imagen"):
                    buf = io.BytesIO()
                    # Convertimos a array para matplotlib
                    img_array = np.array(img_pil)
                    fig, ax = plt.subplots(figsize=(10, 10 * img_pil.height / img_pil.width))
                    ax.imshow(img_array)
                    ax.axis('off')
                    for o in objects:
                        c = patches.Circle((o["left"], o["top"]), radio_px, color=color, alpha=0.3)
                        ax.add_patch(c)
                        ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                    st.download_button("Bajar PNG", buf.getvalue(), "propuesta.png", "image/png")

else:
    st.info("Sube un archivo para empezar.")
