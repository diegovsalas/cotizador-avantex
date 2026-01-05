import streamlit as st
from PIL import Image
import io
import numpy as np
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
    /* Borde gris para identificar el área del canvas */
    iframe {border: 1px solid #ccc;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V16 (Imagen Reconstruida)")

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
        
        # 1. Cargar desde PDF o Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5 es un buen balance
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pil_image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            pil_image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Conversión a RGB estándar
        pil_image = pil_image.convert("RGB")

        # 3. Redimensionar (Max 800px para evitar bloqueos del navegador)
        MAX_WIDTH = 800 
        if pil_image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(pil_image.width))
            h_size = int((float(pil_image.height) * float(w_percent)))
            pil_image = pil_image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        # 4. --- EL SECRETO: LAVADO VÍA NUMPY ---
        # Convertimos la imagen a números (array) y luego VOLVEMOS a crear una imagen PIL.
        # Esto elimina metadatos corruptos, perfiles de color extraños o bloqueos de PDF.
        img_array = np.array(pil_image)
        clean_image = Image.fromarray(img_array)

        st.session_state['bg_image'] = clean_image
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

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
        clean_img = st.session_state['bg_image']
        
        # 1. Vista Previa (Solo verificación)
        st.image(clean_img, caption="Vista Previa", use_column_width=True)
        st.write("---")
        
        # 2. El Canvas
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        
        # SOLUCIÓN: Pasamos 'clean_img' que es un objeto PIL reconstruido.
        # Ya no es una matriz (evita ValueError) y está limpia (evita pantalla negra).
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_image=clean_img, 
            update_streamlit=True,
            height=clean_img.height,
            width=clean_img.width,
            drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # Lógica de Herramientas
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                if modo == "📏 Calibrar Escala":
                    try:
                        o = objects[-1]
                        # Cálculo matemático seguro
                        w = o.get("width", 0) * o.get("scaleX", 1)
                        h = o.get("height", 0) * o.get("scaleY", 1)
                        dist = math.sqrt(w**2 + h**2)
                        
                        st.info(f"Distancia: {dist:.1f} px")
                        m = st.number_input("Metros reales:", 1.0)
                        if st.button("Guardar Escala"):
                            st.session_state['scale_px_per_meter'] = dist / m
                            st.success("Guardado!")
                            st.rerun()
                    except: pass
                
                elif modo == "📍 Sembrar Equipos":
                    st.metric("Total Equipos", len(objects))
                    if st.button("Generar Imagen Final"):
                        buf = io.BytesIO()
                        # Usar el array numérico para matplotlib garantiza compatibilidad
                        img_array = np.array(clean_img)
                        fig, ax = plt.subplots(figsize=(10, 10 * clean_img.height / clean_img.width))
                        ax.imshow(img_array)
                        ax.axis('off')
                        for o in objects:
                            ax.add_patch(patches.Circle((o["left"], o["top"]), radio_px, color=color_hex, alpha=0.3))
                            ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        st.download_button("Descargar Propuesta", buf.getvalue(), "propuesta.png", "image/png")
