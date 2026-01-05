import streamlit as st
from PIL import Image
import io
import base64
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import uuid

# --- 1. EL PARCHE (Vital para que funcione en tu Streamlit actual) ---
# Esto inyecta manualmente la función que falta para conectar la imagen con el editor
import streamlit.elements.image as st_image

def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None):
    buffered = io.BytesIO()
    # Guardamos como PNG para no perder calidad
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

# Aplicamos el parche
st_image.image_to_url = custom_image_to_url

# Ahora sí importamos el canvas
from streamlit_drawable_canvas import st_canvas


# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🌱")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    /* Borde blanco para resaltar el editor */
    iframe {border: 2px solid #ffffff;} 
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V24 (Fondo Blanco + Parche)")

# --- 3. ESTADO ---
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = str(uuid.uuid4())
if 'last_file' not in st.session_state: st.session_state['last_file'] = ""

# --- 4. FUNCIÓN DE LIMPIEZA DE IMAGEN ---
def process_file(uploaded_file):
    try:
        # A) Leer PDF o Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # B) CORRECCIÓN DE FONDO BLANCO (Lo que pediste)
        # Si la imagen no es RGB puro (tiene transparencia), la pegamos sobre blanco.
        if image.mode != "RGB":
            background = Image.new("RGB", image.size, (255, 255, 255)) # Hoja blanca
            if image.mode in ('RGBA', 'LA'):
                # Usamos la transparencia original como máscara
                background.paste(image, mask=image.split()[-1])
            else:
                background.paste(image)
            image = background # Ahora 'image' es el plano sobre blanco
        else:
            # Aunque sea RGB, forzamos la conversión para limpiar metadatos
            image = image.convert("RGB")

        # C) Redimensionar (Seguridad para el navegador)
        MAX_WIDTH = 1000
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        return image

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
        return None

# --- 5. BARRA LATERAL ---
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
    modo = st.radio("Modo:", ["📏 Calibrar Escala", "📍 Sembrar Equipos"])
    
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

# --- 6. APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    # Detectar cambio de archivo
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['last_file'] != file_id:
        st.session_state['bg_image'] = process_file(uploaded_file)
        st.session_state['last_file'] = file_id
        st.session_state['canvas_key'] = str(uuid.uuid4()) # Resetear canvas
        st.rerun()

if st.session_state['bg_image']:
    img_pil = st.session_state['bg_image']
    
    st.write("### Editor de Sembrado")
    st.caption("Si ves el fondo blanco con tu plano, ¡ya funciona!")
    
    # EL CANVAS
    # background_color="#FFFFFF" asegura que el hueco sea blanco, 
    # y 'background_image' pone tu plano encima.
    canvas_result = st_canvas(
        fill_color=color + "55",
        stroke_width=2,
        stroke_color=color,
        background_color="#FFFFFF", # Fondo de seguridad blanco
        background_image=img_pil,   # Tu plano procesado
        update_streamlit=True,
        height=img_pil.height,
        width=img_pil.width,
        drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
        point_display_radius=radio_px,
        display_toolbar=True,
        key=st.session_state['canvas_key']
    )
    
    # LÓGICA
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
                st.metric("Total", len(objects))
                if st.button("Generar Imagen"):
                    buf = io.BytesIO()
                    # Matplotlib también necesita saber que el fondo es blanco
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
