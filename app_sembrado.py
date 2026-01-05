import streamlit as st
from PIL import Image
import io
import numpy as np # Necesario para estabilidad
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import uuid

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

st.title("🛠️ Aromatex: V9 (Corrección de Estabilidad)")

# --- ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale' not in st.session_state: st.session_state['scale'] = 35.0

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
            # Zoom 2.0 y alpha=False (Fondo Blanco)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
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

        # 3. Redimensionar (Max 1200px)
        base_width = 1200
        if image.width > base_width:
            w_percent = (base_width / float(image.width))
            h_size = int((float(image.height) * float(w_percent)))
            image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = image
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Control")
    modo = st.radio("Herramienta", ["Sembrar", "Calibrar"])
    if st.button("🔄 Reiniciar"):
        st.session_state['bg_image'] = None
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
        # Convertimos a Numpy Array para evitar errores de tipo en Streamlit
        img_pil = st.session_state['bg_image']
        img_array = np.array(img_pil)
        
        # --- MUESTRA DE IMAGEN (SOLUCIÓN ERROR) ---
        # Usamos use_column_width=True que es compatible con versiones viejas
        st.image(img_array, caption="Vista Previa", use_column_width=True)
            
        st.divider()
        st.write("### ✏️ Editor")
        
        # --- CANVAS ---
        canvas_result = st_canvas(
            fill_color="rgba(46, 139, 87, 0.3)",
            stroke_width=2,
            stroke_color="#2E8B57",
            background_image=img_pil, # st_canvas maneja bien PIL
            update_streamlit=True,
            height=img_pil.height,
            width=img_pil.width,
            drawing_mode="point" if modo == "Sembrar" else "line",
            point_display_radius=15,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        if canvas_result.json_data and canvas_result.json_data["objects"]:
            st.success(f"Objetos marcados: {len(canvas_result.json_data['objects'])}")
            
    else:
        st.warning("Esperando procesamiento de imagen...")
