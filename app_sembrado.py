import streamlit as st
from PIL import Image
import io
import numpy as np
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import uuid

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

st.title("🌱 Aromatex: V10 (Canvas Optimizado)")

# --- ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        # Resetear puntero
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        image = None
        
        # 1. Procesar PDF o Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5 es suficiente para canvas (equilibrio calidad/rendimiento)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Asegurar Fondo Blanco y RGB
        if image.mode != "RGB":
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                bg.paste(image, mask=image.convert("RGBA").split()[3])
            else:
                bg.paste(image)
            image = bg
        else:
            image = image.convert("RGB")

        # 3. --- REDIMENSIONADO AGRESIVO PARA CANVAS ---
        # El Canvas HTML5 falla con imágenes gigantes. Limitamos a 1000px de ancho.
        # Esto NO afecta la calidad de la descarga final (si quisieras guardarla aparte),
        # pero es necesario para que el editor sea visible y fluido.
        MAX_WIDTH = 1000 
        if image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(image.width))
            h_size = int((float(image.height) * float(w_percent)))
            image = image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = image
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    
    # Selector de equipo
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
    modo = st.radio("Herramienta", ["📏 Calibrar", "📍 Sembrar"])
    
    st.divider()
    # Escala manual
    nuevo_scale = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if nuevo_scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = nuevo_scale
        st.rerun()

    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio: {radio_real}m ({radio_px} px)")

    if st.button("🔄 Reiniciar Todo"):
        st.session_state['bg_image'] = None
        st.session_state['last_file'] = None
        st.rerun()

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF/PNG/JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    # Detectar cambio de archivo
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        img_pil = st.session_state['bg_image']
        
        # 1. Vista Previa (Solo para confirmar)
        st.image(np.array(img_pil), caption="Vista Previa (Cargada correctamente)", use_column_width=True)
            
        st.write("---")
        st.subheader("✏️ Editor de Sembrado")
        st.caption("Si ves la imagen arriba, ahora deberías verla abajo para editar.")
        
        # 2. El Editor (Canvas)
        canvas_result = st_canvas(
            fill_color=color_hex + "44",  # Color con transparencia
            stroke_width=2,
            stroke_color=color_hex,
            background_image=img_pil,
            update_streamlit=True,
            height=img_pil.height,
            width=img_pil.width,
            drawing_mode="point" if modo == "📍 Sembrar" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # Lógica de Calibración
        if modo == "📏 Calibrar" and canvas_result.json_data and canvas_result.json_data["objects"]:
            obj = canvas_result.json_data["objects"][-1]
            # Distancia simple (hipotenusa)
            dist_px = math.sqrt((obj["width"] * obj["scaleX"])**2 + (obj["height"] * obj["scaleY"])**2)
            st.info(f"Distancia dibujada: {dist_px:.1f} px")
            
            metros = st.number_input("¿Cuántos metros son?", value=1.0, key="calib_input")
            if st.button("Guardar Escala"):
                st.session_state['scale_px_per_meter'] = dist_px / metros
                st.success(f"Escala guardada: {st.session_state['scale_px_per_meter']:.2f} px/m")
                st.rerun()
                
        # Lógica de Conteo
        elif modo == "📍 Sembrar" and canvas_result.json_data and canvas_result.json_data["objects"]:
            cantidad = len(canvas_result.json_data["objects"])
            st.metric("Equipos Sembrados", cantidad)
            
    else:
        st.warning("Procesando imagen...")
