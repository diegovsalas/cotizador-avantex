import streamlit as st
from PIL import Image
import io
import numpy as np
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import uuid
import math  # <--- IMPORTANTE: Esto arregla el NameError

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

st.title("🌱 Aromatex: V11 (Versión Estable)")

# --- ESTADO (SESSION STATE) ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'img_id' not in st.session_state: st.session_state['img_id'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- PROCESAMIENTO DE ARCHIVO ---
def process_file(uploaded_file):
    try:
        # Resetear lectura del archivo
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        
        image = None
        
        # 1. Convertir PDF o abrir Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x (Balance calidad/rendimiento)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(io.BytesIO(file_bytes))
            
        # 2. Forzar RGB (Eliminar transparencias problemáticas)
        if image.mode != "RGB":
            bg = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                bg.paste(image, mask=image.convert("RGBA").split()[3])
            else:
                bg.paste(image)
            image = bg
        else:
            image = image.convert("RGB")

        # 3. Redimensionar para el Editor (Max 1000px ancho)
        # Esto asegura que el Canvas no se congele por exceso de tamaño
        MAX_WIDTH = 1000 
        if image.width > MAX_WIDTH:
            w_percent = (MAX_WIDTH / float(image.width))
            h_size = int((float(image.height) * float(w_percent)))
            image = image.resize((MAX_WIDTH, h_size), Image.Resampling.LANCZOS)

        st.session_state['bg_image'] = image
        st.session_state['img_id'] = str(uuid.uuid4()) # Forzar nueva ID para recargar canvas
        
    except Exception as e:
        st.error(f"Error al procesar imagen: {e}")

# --- BARRA LATERAL (CONTROLES) ---
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
    modo = st.radio("Herramienta", ["📏 Calibrar", "📍 Sembrar"])
    
    st.divider()
    # Input manual de escala
    val_escala = st.number_input("Escala (Px por metro):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if val_escala != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = val_escala
        st.rerun()

    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio visual: {radio_px} px")

    if st.button("🗑️ Resetear Todo"):
        st.session_state['bg_image'] = None
        st.session_state['last_file'] = None
        st.rerun()

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG, PNG)", type=["pdf", "png", "jpg"])

if uploaded_file:
    # Detectar si cambió el archivo
    file_key = f"{uploaded_file.name}_{uploaded_file.size}"
    if 'last_file' not in st.session_state or st.session_state['last_file'] != file_key:
        process_file(uploaded_file)
        st.session_state['last_file'] = file_key
        st.rerun()

    if st.session_state['bg_image']:
        img_pil = st.session_state['bg_image']
        
        # 1. Vista Previa (Testigo)
        with st.expander("👁️ Ver imagen original cargada", expanded=False):
            st.image(np.array(img_pil), use_column_width=True)
            
        st.write("### ✏️ Editor de Plano")
        
        # 2. Editor Canvas
        # Background color blanco forzado para evitar invisibilidad
        canvas_result = st_canvas(
            fill_color=color_hex + "44",
            stroke_width=2,
            stroke_color=color_hex,
            background_color="#FFFFFF", # Fondo blanco detrás de la imagen
            background_image=img_pil,
            update_streamlit=True,
            height=img_pil.height,
            width=img_pil.width,
            drawing_mode="point" if modo == "📍 Sembrar" else "line",
            point_display_radius=radio_px,
            display_toolbar=True,
            key=f"canvas_{st.session_state['img_id']}"
        )
        
        # 3. Lógica de Datos (Protegida contra errores)
        if canvas_result.json_data and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            
            if len(objects) > 0:
                # --- MODO CALIBRAR ---
                if modo == "📏 Calibrar":
                    obj = objects[-1]
                    try:
                        # Cálculo protegido
                        # Obtenemos ancho y alto escalados
                        w = obj.get("width", 0) * obj.get("scaleX", 1)
                        h = obj.get("height", 0) * obj.get("scaleY", 1)
                        # Hipotenusa
                        dist_px = math.sqrt(w**2 + h**2)
                        
                        st.info(f"📏 Distancia detectada: {dist_px:.1f} píxeles")
                        
                        real_m = st.number_input("Metros reales:", value=1.0, min_value=0.1)
                        if st.button("Guardar Escala"):
                            st.session_state['scale_px_per_meter'] = dist_px / real_m
                            st.success("Escala Guardada!")
                            st.rerun()
                            
                    except Exception as e:
                        st.warning("Dibuja una línea recta clara para calibrar.")

                # --- MODO SEMBRAR ---
                elif modo == "📍 Sembrar":
                    count = len(objects)
                    st.metric("Difusores colocados", count)
                    
                    # Botón para descargar resultado
                    if st.button("Generar Imagen Final"):
                        buf = io.BytesIO()
                        # Crear figura limpia
                        fig, ax = plt.subplots(figsize=(10, 10 * img_pil.height / img_pil.width))
                        ax.imshow(img_pil)
                        ax.axis('off')
                        
                        # Redibujar puntos
                        for o in objects:
                            x, y = o["left"], o["top"]
                            # Círculo cobertura
                            ax.add_patch(patches.Circle((x, y), radio_px, color=color_hex, alpha=0.3))
                            # Punto centro
                            ax.add_patch(patches.Circle((x, y), 5, color="white"))
                            
                        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                        buf.seek(0)
                        st.download_button("📥 Descargar", buf, "propuesta.png", "image/png")
    else:
        st.info("Procesando imagen...")
