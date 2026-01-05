import streamlit as st
from PIL import Image
import io
import numpy as np  # <--- LA CLAVE DE ESTA SOLUCIÓN
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import uuid
import math

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V15 (Modo Matriz Numérica)")

# --- ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        pil_image = None
        
        # 1. Cargar PDF o Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pil_image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            pil_image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Convertir a RGB puro (3 canales: Rojo, Verde, Azul)
        # Esto elimina el canal Alfa (transparencia) que suele causar la pantalla negra
        pil_image = pil_image.convert("RGB")

        # 3. Redimensionar (Ancho fijo 800px)
        MAX_WIDTH = 800 
        if pil_image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(pil_image.width))
            h_size = int((float(pil_image.height) * float(w_percent)))
            pil_image = pil_image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = pil_image
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    tipo_equipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
    if "Home" in tipo_equipo:
        radio_real = 5.6
        color_hex = "#2E8B57"
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color_hex = "#FF8C00"
    else:
        radio_real = 16.0
        color_hex = "#DC143C"
        
    st.divider()
    modo = st.radio("Herramienta", ["📏 Calibrar Escala", "📍 Sembrar Equipos"])
    
    nuevo_scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if nuevo_scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = nuevo_scale
        st.rerun()

    if st.button("🗑️ Reiniciar"):
        st.session_state['bg_image'] = None
        st.session_state['last_file'] = None
        st.rerun()

# --- APP ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        pil_img = st.session_state['bg_image']
        
        # --- PASO CRÍTICO: CONVERSIÓN A MATRIZ ---
        # Convertimos la imagen en un array numérico de Numpy.
        # El componente canvas entiende esto nativamente.
        img_array = np.array(pil_img)

        # 1. Vista Previa
        st.image(img_array, caption="Vista Previa", use_column_width=True)
        st.write("---")
        
        # 2. El Canvas
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_image=img_array, # <--- ENVIAMOS LA MATRIZ, NO LA IMAGEN PIL
            update_streamlit=True,
            height=pil_img.height,
            width=pil_img.width,
            drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # Lógica
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                if modo == "📏 Calibrar Escala":
                    try:
                        o = objects[-1]
                        dist = math.sqrt((o["width"]*o["scaleX"])**2 + (o["height"]*o["scaleY"])**2)
                        st.info(f"Distancia: {dist:.1f} px")
                        m = st.number_input("Metros reales:", 1.0)
                        if st.button("Guardar Escala"):
                            st.session_state['scale_px_per_meter'] = dist / m
                            st.rerun()
                    except: pass
                
                elif modo == "📍 Sembrar Equipos":
                    st.metric("Total", len(objects))
                    if st.button("Generar Imagen"):
                        buf = io.BytesIO()
                        fig, ax = plt.subplots(figsize=(10, 10 * pil_img.height / pil_img.width))
                        ax.imshow(img_array)
                        ax.axis('off')
                        for o in objects:
                            ax.add_patch(patches.Circle((o["left"], o["top"]), radio_px, color=color_hex, alpha=0.3))
                            ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        st.download_button("Descargar", buf.getvalue(), "plano.png", "image/png")
