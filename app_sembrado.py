import streamlit as st
from PIL import Image
import io
import base64
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import uuid

# --- 1. PARCHE DE COMPATIBILIDAD (CRÍTICO) ---
# Esto hace que el editor funcione aunque tengas una versión nueva de Streamlit
import streamlit.elements.image as st_image

def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

st_image.image_to_url = custom_image_to_url
# ---------------------------------------------

from streamlit_drawable_canvas import st_canvas

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    /* Borde blanco grueso para asegurar que ves el área del editor */
    iframe {border: 2px solid #ffffff;} 
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V26 (Fondo Blanco Forzado)")

# --- ESTADO ---
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = str(uuid.uuid4())
if 'last_file' not in st.session_state: st.session_state['last_file'] = ""

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        image = None
        uploaded_file.seek(0)
        
        # A) PDF a Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            # Alpha=True para capturar transparencias
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # B) EL "APLANADOR" (SOLUCIÓN A PANTALLA NEGRA)
        # 1. Convertimos a RGBA para manejar capas
        image = image.convert("RGBA")
        # 2. Creamos una hoja totalmente BLANCA del mismo tamaño
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        # 3. Pegamos el plano encima (usando la transparencia como máscara)
        # Esto rellena lo transparente con blanco
        final_image = Image.alpha_composite(background, image)
        # 4. Convertimos a RGB simple (eliminamos el canal transparente)
        final_image = final_image.convert("RGB")

        # C) Redimensionar (Para que no se congele el navegador)
        MAX_WIDTH = 1000
        if final_image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(final_image.width)
            h = int(float(final_image.height) * float(ratio))
            final_image = final_image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        return final_image

    except Exception as e:
        st.error(f"Error: {e}")
        return None

# --- SIDEBAR ---
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
        st.session_state['last_file'] = ""
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

# --- APP ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['last_file'] != file_id:
        st.session_state['bg_image'] = process_file(uploaded_file)
        st.session_state['last_file'] = file_id
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

if st.session_state['bg_image']:
    img_pil = st.session_state['bg_image']
    
    st.write("### Editor Interactivo")
    
    # EL CANVAS
    # Usamos background_color="#FFFFFF" como doble seguridad
    canvas_result = st_canvas(
        fill_color=color + "55",
        stroke_width=2,
        stroke_color=color,
        background_color="#FFFFFF",
        background_image=img_pil,
        update_streamlit=True,
        height=img_pil.height,
        width=img_pil.width,
        drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
        point_display_radius=radio_px,
        display_toolbar=True,
        key=st.session_state['canvas_key']
    )
    
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
                st.metric("Total Equipos", len(objects))
                if st.button("Generar Imagen"):
                    buf = io.BytesIO()
                    fig, ax = plt.subplots(figsize=(10, 10 * img_pil.height / img_pil.width))
                    ax.imshow(img_pil)
                    ax.axis('off')
                    for o in objects:
                        c = patches.Circle((o["left"], o["top"]), radio_px, color=color, alpha=0.3)
                        ax.add_patch(c)
                        ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                    st.download_button("Descargar PNG", buf.getvalue(), "propuesta.png", "image/png")

else:
    st.info("Sube un archivo para empezar.")
