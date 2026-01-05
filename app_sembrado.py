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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    /* Borde blanco sutil para delimitar el canvas si el fondo es negro */
    iframe {border: 1px solid #555;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V13 (Sanitización de Memoria)")

# --- GESTIÓN DE ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO (LA MAGIA ESTÁ AQUÍ) ---
def process_file(uploaded_file):
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        raw_image = None
        
        # 1. Leer PDF o Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            raw_image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            raw_image = Image.open(io.BytesIO(file_bytes))
            
        # 2. "Planchado" de imagen (Fondo Blanco + RGB)
        # Esto elimina transparencias rotas
        if raw_image.mode != "RGB":
            bg = Image.new("RGB", raw_image.size, (255, 255, 255))
            if raw_image.mode in ('RGBA', 'LA') or (raw_image.mode == 'P' and 'transparency' in raw_image.info):
                bg.paste(raw_image, mask=raw_image.convert("RGBA").split()[3])
            else:
                bg.paste(raw_image)
            raw_image = bg
        else:
            raw_image = raw_image.convert("RGB")

        # 3. Redimensionar (Seguridad)
        MAX_WIDTH = 800 
        if raw_image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(raw_image.width))
            h_size = int((float(raw_image.height) * float(w_percent)))
            raw_image = raw_image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        # 4. --- SANITIZACIÓN FINAL (NUEVO PASO CRÍTICO) ---
        # Guardamos la imagen en un buffer y la recargamos.
        # Esto elimina metadatos corruptos del PDF que confunden al Canvas.
        buf = io.BytesIO()
        raw_image.save(buf, format="PNG")
        buf.seek(0)
        
        final_image = Image.open(buf)
        final_image.load() # Forzar carga en memoria RAM
        
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

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, PNG, JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        img_pil = st.session_state['bg_image']
        
        # --- DEBUG VISUAL ---
        # Si esta imagen se ve, el problema es 100% comunicación con el canvas
        st.image(img_pil, caption=f"Imagen Procesada ({img_pil.width}x{img_pil.height}px - {img_pil.mode})", use_column_width=True)
        
        st.write("---")
        st.write("### ✏️ Editor Interactivo")
        
        # --- CANVAS ---
        # Quitamos background_color para evitar conflictos visuales
        # Si la imagen falla, ahora veremos el fondo por defecto (transparente)
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_image=img_pil, 
            update_streamlit=True,
            height=img_pil.height,
            width=img_pil.width,
            drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            
            if len(objects) > 0:
                if modo == "📏 Calibrar Escala":
                    try:
                        obj = objects[-1]
                        # Cálculos protegidos
                        scale_x = obj.get("scaleX", 1)
                        scale_y = obj.get("scaleY", 1)
                        w = obj.get("width", 0) * scale_x
                        h = obj.get("height", 0) * scale_y
                        
                        dist_px = math.sqrt(w**2 + h**2)
                        st.info(f"📏 Distancia: {dist_px:.1f} px")
                        
                        metros = st.number_input("Metros reales:", value=1.0)
                        if st.button("Guardar Escala"):
                            st.session_state['scale_px_per_meter'] = dist_px / metros
                            st.success("Guardado!")
                            st.rerun()
                    except Exception:
                        pass # Ignorar errores de dibujo incompleto

                elif modo == "📍 Sembrar Equipos":
                    st.metric("Equipos", len(objects))
                    
                    if st.button("📸 Generar Imagen"):
                        buf = io.BytesIO()
                        fig, ax = plt.subplots(figsize=(10, 10 * img_pil.height / img_pil.width))
                        ax.imshow(img_pil)
                        ax.axis('off')
                        for o in objects:
                            x, y = o["left"], o["top"]
                            ax.add_patch(patches.Circle((x, y), radio_px, color=color_hex, alpha=0.3))
                            ax.add_patch(patches.Circle((x, y), 5, color="white"))
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        buf.seek(0)
                        st.download_button("Descargar", buf, "propuesta.png", "image/png")
    else:
        st.info("Sube un archivo para comenzar.")
