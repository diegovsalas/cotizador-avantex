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
    iframe {border: 1px solid #555;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V14 (Compatibilidad Web)")

# --- ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        raw_image = None
        
        # 1. Carga inicial
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            raw_image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            raw_image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Conversión a RGBA (Mejor compatibilidad con navegadores)
        # Convertimos todo a RGBA explícitamente para que el canvas no tenga dudas
        raw_image = raw_image.convert("RGBA")

        # 3. Poner fondo blanco si es transparente
        # Creamos una capa blanca y pegamos la imagen encima
        background = Image.new("RGBA", raw_image.size, (255, 255, 255, 255))
        final_image = Image.alpha_composite(background, raw_image)

        # 4. Redimensionar (Max 800px)
        MAX_WIDTH = 800 
        if final_image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(final_image.width))
            h_size = int((float(final_image.height) * float(w_percent)))
            final_image = final_image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = final_image
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando: {e}")

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
    
    st.divider()
    nuevo_scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if nuevo_scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = nuevo_scale
        st.rerun()

    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio visual: {radio_px} px")
    
    if st.button("🗑️ Reiniciar"):
        st.session_state['bg_image'] = None
        st.session_state['last_file'] = None
        st.rerun()

# --- APP ---
uploaded_file = st.file_uploader("Sube plano (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        img_pil = st.session_state['bg_image']
        
        st.image(img_pil, caption="Vista Previa", use_column_width=True)
        st.write("---")
        
        # EL CANVAS
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_image=img_pil, # Ahora es RGBA puro
            update_streamlit=True,
            height=img_pil.height,
            width=img_pil.width,
            drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # Logica
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                if modo == "📏 Calibrar Escala":
                    try:
                        obj = objects[-1]
                        dist_px = math.sqrt((obj["width"]*obj["scaleX"])**2 + (obj["height"]*obj["scaleY"])**2)
                        st.info(f"Distancia: {dist_px:.1f} px")
                        m = st.number_input("Metros reales:", 1.0)
                        if st.button("Guardar Escala"):
                            st.session_state['scale_px_per_meter'] = dist_px / m
                            st.rerun()
                    except: pass
                elif modo == "📍 Sembrar Equipos":
                    st.metric("Total", len(objects))
                    if st.button("Generar Imagen"):
                        buf = io.BytesIO()
                        fig, ax = plt.subplots(figsize=(10, 10 * img_pil.height / img_pil.width))
                        ax.imshow(img_pil)
                        ax.axis('off')
                        for o in objects:
                            ax.add_patch(patches.Circle((o["left"], o["top"]), radio_px, color=color_hex, alpha=0.3))
                            ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        st.download_button("Descargar", buf.getvalue(), "mapa.png", "image/png")
