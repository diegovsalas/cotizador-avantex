import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🌱")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1 {color: #2E8B57;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: V7 (Corrección de Lectura)")

# --- ESTADO ---
if 'scale_px_per_meter' not in st.session_state:
    st.session_state['scale_px_per_meter'] = 35.0 
if 'bg_image' not in st.session_state:
    st.session_state['bg_image'] = None
if 'file_hash' not in st.session_state:
    st.session_state['file_hash'] = None

# --- FUNCIÓN DE CARGA ROBUSTA ---
def load_image_robust(uploaded_file):
    # Generamos un ID único para el archivo para evitar recargas innecesarias
    file_id = uploaded_file.file_id if hasattr(uploaded_file, 'file_id') else uploaded_file.name
    
    if st.session_state['file_hash'] != file_id:
        try:
            image = None
            
            # 1. Obtener bytes de forma segura (resetear puntero)
            uploaded_file.seek(0)
            file_bytes = uploaded_file.getvalue()
            
            if uploaded_file.type == "application/pdf":
                # Renderizar PDF
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page = doc.load_page(0)
                
                # Usamos 1.5 de zoom (buen balance calidad/memoria)
                mat = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=mat, alpha=False) # alpha=False fuerza fondo blanco
                
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))
            else:
                # Renderizar Imagen Directa
                image = Image.open(io.BytesIO(file_bytes))

            # 2. Normalizar a RGB y Fondo Blanco (Crucial para PNGs transparentes)
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                background = Image.new("RGB", image.size, (255, 255, 255))
                # Usar el canal alfa como máscara si existe, sino pegar directo
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[3])
                else:
                    background.paste(image)
                image = background
            else:
                image = image.convert("RGB")

            # 3. Redimensionar (Evita crash por memoria en planos gigantes)
            base_width = 1200
            w_percent = (base_width / float(image.size[0]))
            h_size = int((float(image.size[1]) * float(w_percent)))
            image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
            
            # Guardar en estado
            st.session_state['bg_image'] = image
            st.session_state['file_hash'] = file_id
            
        except Exception as e:
            st.error(f"❌ Error crítico cargando archivo: {e}")
            st.session_state['bg_image'] = None

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
        
    canvas_fill = color_hex + "44"
    
    st.divider()
    modo = st.radio("Modo:", ["📏 Calibrar", "📍 Sembrar"], index=1)
    
    st.divider()
    escala_manual = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if escala_manual != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = escala_manual
        st.rerun()
        
    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio: {radio_real}m ({radio_px} px)")
    
    if st.button("🗑️ Limpiar Memoria"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# --- APP ---
archivo = st.file_uploader("Sube tu plano", type=["pdf", "jpg", "png"])

if archivo:
    load_image_robust(archivo)
    
    if st.session_state['bg_image']:
        img = st.session_state['bg_image']
        
        # MODO CALIBRAR
        if modo == "📏 Calibrar":
            st.info("Dibuja una línea de referencia.")
            canvas = st_canvas(
                fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="blue",
                background_image=img, update_streamlit=True,
                height=img.height, width=img.width, drawing_mode="line",
                display_toolbar=True, key="calib"
            )
            if canvas.json_data and canvas.json_data["objects"]:
                obj = canvas.json_data["objects"][-1]
                # Pitagoras simple ignorando transformaciones complejas de canvas
                dist = math.sqrt((obj["width"] * obj["scaleX"])**2 + (obj["height"] * obj["scaleY"])**2)
                st.write(f"Px: {dist:.1f}")
                metros = st.number_input("Metros reales:", 1.0)
                if st.button("Guardar Escala"):
                    st.session_state['scale_px_per_meter'] = dist / metros
                    st.success("Guardado!")
                    st.rerun()

        # MODO SEMBRAR
        elif modo == "📍 Sembrar":
            st.success(f"Sembrando: {tipo_equipo}")
            canvas = st_canvas(
                fill_color=canvas_fill, stroke_width=2, stroke_color=color_hex,
                background_image=img, update_streamlit=True,
                height=img.height, width=img.width, drawing_mode="point",
                point_display_radius=radio_px, display_toolbar=True,
                key=f"sembrado_{tipo_equipo}_{st.session_state['scale_px_per_meter']}"
            )
            
            if canvas.json_data and canvas.json_data["objects"]:
                conteo = len(canvas.json_data["objects"])
                st.write(f"**Total Equipos: {conteo}**")
                
                # Generar Imagen
                fig, ax = plt.subplots(figsize=(10, 10 * img.height / img.width))
                ax.imshow(img)
                ax.axis('off')
                for obj in canvas.json_data["objects"]:
                    x, y = obj["left"], obj["top"]
                    ax.add_patch(patches.Circle((x, y), radio_px, color=color_hex, alpha=0.3))
                    ax.add_patch(patches.Circle((x, y), 5, color="white"))
                
                buf = io.BytesIO()
                plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=100)
                buf.seek(0)
                st.download_button("Descargar JPG", data=buf, file_name="propuesta.png", mime="image/png")
    else:
        st.warning("El archivo se subió pero no se pudo generar la imagen. Intenta subir un JPG en lugar del PDF.")
