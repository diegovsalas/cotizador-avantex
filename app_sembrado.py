import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import uuid

# --- 1. DIAGNÓSTICO DE VERSIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🌱")

# Verificamos qué versión está corriendo el servidor
ver = st.__version__
if ver != "1.34.0":
    st.error(f"⚠️ VERSIÓN INCOMPATIBLE DETECTADA: {ver}")
    st.warning("Para que el editor funcione, necesitas 'streamlit==1.34.0' en tu requirements.txt y REINICIAR la app.")
else:
    st.success(f"✅ Versión correcta detectada: {ver}. El editor debería funcionar.")

# --- 2. ESTILOS Y ESTADO ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    /* Borde blanco para resaltar el editor en modo oscuro */
    iframe {border: 2px solid #ffffff;} 
    </style>
    """, unsafe_allow_html=True)

if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = str(uuid.uuid4())
if 'last_file_id' not in st.session_state: st.session_state['last_file_id'] = ""

# --- 3. PROCESAMIENTO ROBUSTO ---
def process_file(uploaded_file):
    try:
        # A) Cargar PDF o Imagen
        image = None
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()

        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x (Calidad óptima)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(io.BytesIO(file_bytes))

        # B) CORRECCIÓN DE FONDO BLANCO (Vital para planos negros/transparentes)
        # Convertimos siempre a RGBA para manejar capas
        image = image.convert("RGBA")
        # Creamos lienzo blanco
        new_bg = Image.new("RGBA", image.size, "WHITE")
        # Pegamos el plano encima
        new_bg.alpha_composite(image)
        # Convertimos a RGB final
        final_image = new_bg.convert("RGB")

        # C) Redimensionar (Evita bloqueos del navegador)
        MAX_WIDTH = 1000
        if final_image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(final_image.width)
            h = int(float(final_image.height) * float(ratio))
            final_image = final_image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        return final_image

    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

# --- 4. BARRA LATERAL ---
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
        st.session_state['last_file_id'] = ""
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

# --- 5. APP PRINCIPAL ---
st.title("🌱 Sembrado Aromatex")

uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    # Detectar cambio de archivo
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['last_file_id'] != file_id:
        st.session_state['bg_image'] = process_file(uploaded_file)
        st.session_state['last_file_id'] = file_id
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

if st.session_state['bg_image']:
    img_pil = st.session_state['bg_image']
    
    # 1. Editor de Sembrado
    st.write("### Editor Interactivo")
    
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
    
    # 2. Lógica de Resultados
    if canvas_result.json_data and "objects" in canvas_result.json_data:
        objects = canvas_result.json_data["objects"]
        if len(objects) > 0:
            
            # CALIBRACIÓN
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
            
            # SEMBRADO
            elif modo == "📍 Sembrar Equipos":
                st.metric("Total Equipos", len(objects))
                
                if st.button("Generar Imagen"):
                    buf = io.BytesIO()
                    # Usamos matplotlib para asegurar calidad final
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
    st.info("👆 Sube tu plano para comenzar.")
