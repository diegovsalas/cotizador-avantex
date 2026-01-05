import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import uuid # Para generar IDs únicos y forzar recarga

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Diagnóstico", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

st.title("🛠️ Aromatex: V8 (Diagnóstico de Imagen)")

# --- ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale' not in st.session_state: st.session_state['scale'] = 35.0

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        # Resetear el puntero del archivo por seguridad
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        image = None
        
        # 1. Detección de Formato
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 2.0 y alpha=False (Fondo Blanco forzado)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            # Es PNG/JPG
            image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Normalización (Evitar transparencias negras)
        if image.mode != "RGB":
            # Crear fondo blanco
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                # Usar canal alfa como máscara
                bg.paste(image, mask=image.convert("RGBA").split()[3])
            else:
                bg.paste(image)
            image = bg
        else:
            # Incluso si dice RGB, forzamos la conversión para eliminar metadatos raros
            image = image.convert("RGB")

        # 3. Redimensionar (Seguridad para Web)
        # Si la imagen mide más de 1200px, la bajamos.
        base_width = 1200
        if image.width > base_width:
            w_percent = (base_width / float(image.width))
            h_size = int((float(image.height) * float(w_percent)))
            image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = image
        # Generar un ID nuevo para obligar al canvas a repintarse
        st.session_state['img_id'] = str(uuid.uuid4())
        
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Control")
    modo = st.radio("Herramienta", ["Sembrar", "Calibrar"])
    if st.button("🔄 Borrar y Reiniciar"):
        st.session_state['bg_image'] = None
        st.rerun()

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF/PNG/JPG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    # Procesar solo si es un archivo nuevo o no hay imagen cargada
    # (Usamos el nombre y tamaño para detectar cambio)
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        img = st.session_state['bg_image']
        
        # --- PRUEBA TESTIGO (DEBUG) ---
        with st.expander("📸 Verificación de Imagen (Si ves esto, la carga funciona)", expanded=True):
            st.write("Si ves la imagen aquí abajo pero NO en el editor, es un bug visual del editor.")
            st.image(img, use_container_width=True)
            
        st.divider()
        st.write("### ✏️ Editor de Sembrado")
        
        # --- EL CANVAS ---
        # IMPORTANTE: El 'key' incluye el ID único de la imagen. 
        # Si cambia la imagen, cambia el Key, y el canvas se destruye y reconstruye.
        canvas_result = st_canvas(
            fill_color="rgba(46, 139, 87, 0.3)",
            stroke_width=2,
            stroke_color="#2E8B57",
            background_image=img,
            update_streamlit=True,
            height=img.height,
            width=img.width,
            drawing_mode="point" if modo == "Sembrar" else "line",
            point_display_radius=15,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}" 
        )
        
        # Mostrar resultados del canvas
        if canvas_result.json_data and canvas_result.json_data["objects"]:
            n_obj = len(canvas_result.json_data["objects"])
            st.info(f"Objetos en el mapa: {n_obj}")
            
    else:
        st.warning("El archivo se subió pero no se pudo generar la imagen.")
