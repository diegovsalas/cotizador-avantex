import streamlit as st
from PIL import Image
import io
import os
import numpy as np # <--- AGREGADO: Esto faltaba y causaba el error
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
    /* Borde blanco sutil para ver el canvas en modo oscuro */
    iframe {border: 1px solid #ffffff44;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V18 (Corregido)")

# --- ESTADO ---
if 'img_path' not in st.session_state: st.session_state['img_path'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        # 1. Leer el archivo
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        pil_image = None
        
        # 2. Convertir PDF a Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pil_image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            pil_image = Image.open(io.BytesIO(file_bytes))
            
        # 3. Normalizar Imagen (RGB y Tamaño)
        pil_image = pil_image.convert("RGB")
        
        MAX_WIDTH = 800
        if pil_image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(pil_image.width))
            h_size = int((float(pil_image.height) * float(w_percent)))
            pil_image = pil_image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        # 4. GUARDAR EN DISCO (Solución de memoria)
        temp_filename = "temp_plano_render.png"
        pil_image.save(temp_filename, format="PNG")
        
        st.session_state['img_path'] = temp_filename
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
        st.session_state['img_path'] = None
        st.session_state['last_file'] = None
        if os.path.exists("temp_plano_render.png"):
            os.remove("temp_plano_render.png")
        st.rerun()

# --- APP ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['img_path'] and os.path.exists(st.session_state['img_path']):
        # Cargar desde disco
        bg_image_obj = Image.open(st.session_state['img_path'])
        
        # Vista Previa
        st.image(bg_image_obj, caption="Vista Previa", use_column_width=True)
        st.write("---")
        
        # CANVAS
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_image=bg_image_obj,
            update_streamlit=True,
            height=bg_image_obj.height,
            width=bg_image_obj.width,
            drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # LÓGICA
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
                    if st.button("Generar Imagen Final"):
                        buf = io.BytesIO()
                        # Aquí usamos np, que ahora sí está importado
                        img_array = np.array(bg_image_obj)
                        
                        fig, ax = plt.subplots(figsize=(10, 10 * bg_image_obj.height / bg_image_obj.width))
                        ax.imshow(img_array)
                        ax.axis('off')
                        for o in objects:
                            ax.add_patch(patches.Circle((o["left"], o["top"]), radio_px, color=color_hex, alpha=0.3))
                            ax.add_patch(patches.Circle((o["left"], o["top"]), 5, color="white"))
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        st.download_button("Descargar", buf.getvalue(), "propuesta.png", "image/png")
