import streamlit as st
from PIL import Image
import io
import base64
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

# --- 1. PARCHE DE COMPATIBILIDAD (Vital para que no salga error) ---
# Esto arregla el conflicto entre tu Streamlit nuevo y el Canvas antiguo
import streamlit.elements.image as st_image
def custom_image_to_url(image, width=None, clamp=False, channels="RGB", output_format="JPEG", image_id=None):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"
st_image.image_to_url = custom_image_to_url
from streamlit_drawable_canvas import st_canvas

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🌱")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1 {color: #2E8B57;}
    iframe {border: 1px solid #ddd;} /* Borde para ver el canvas */
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Inteligente")

# --- GESTIÓN DE ESTADO ---
if 'scale_px_per_meter' not in st.session_state:
    st.session_state['scale_px_per_meter'] = 35.0 
if 'bg_image' not in st.session_state:
    st.session_state['bg_image'] = None
if 'original_file_name' not in st.session_state:
    st.session_state['original_file_name'] = ""

# --- FUNCIONES AUXILIARES (CON ARREGLO DE FONDO BLANCO) ---
def load_image(uploaded_file):
    if uploaded_file.name != st.session_state['original_file_name']:
        image = None
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, alpha=True) # Alpha=True para detectar transparencia
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
        else:
            image = Image.open(uploaded_file)
        
        # --- EL ARREGLO DE PANTALLA NEGRA ---
        # Si la imagen tiene transparencia, le ponemos fondo blanco
        if image.mode != "RGB":
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode in ('RGBA', 'LA'):
                background.paste(image, mask=image.split()[-1]) # Usar transparencia como máscara
            else:
                background.paste(image)
            image = background
        else:
            image = image.convert("RGB")
        
        # Redimensionar seguro (Max 1000px ancho)
        base_width = 1000
        w_percent = (base_width / float(image.size[0]))
        h_size = int((float(image.size[1]) * float(w_percent)))
        image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
        
        st.session_state['bg_image'] = image
        st.session_state['original_file_name'] = uploaded_file.name

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933190.png", width=50)
    st.header("1. Configuración")
    
    tipo_equipo = st.selectbox("Modelo de Difusor", 
        ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
    if "Home" in tipo_equipo:
        radio_real = 5.6
        color_hex = "#2E8B57" 
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color_hex = "#FF8C00" 
    else:
        radio_real = 16.0
        color_hex = "#DC143C" 

    canvas_fill_color = color_hex + "44"  

    st.divider()
    modo = st.radio("Modo de trabajo:", ["📏 Calibrar Escala", "📍 Sembrar Equipos"], index=1)
    
    st.divider()
    # Opción manual extra
    nuevo_scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if nuevo_scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = nuevo_scale
        st.rerun()

    radio_px_pantalla = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio: {radio_real}m ({radio_px_pantalla} px)")

    if st.button("🗑️ Limpiar Todo"):
        st.session_state['bg_image'] = None
        st.session_state['original_file_name'] = ""
        st.rerun()

# --- ÁREA PRINCIPAL ---
archivo = st.file_uploader("Sube el plano arquitectónico (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if archivo:
    load_image(archivo)
    
    if st.session_state['bg_image']:
        img = st.session_state['bg_image']
        
        # --- MODO CALIBRACIÓN ---
        if modo == "📏 Calibrar Escala":
            st.info("💡 Dibuja una línea de referencia.")
            
            canvas_calib = st_canvas(
                fill_color="rgba(0, 0, 0, 0)",
                stroke_width=3,
                stroke_color="#0000FF",
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="line",
                display_toolbar=True, # Agregado Zoom
                key="canvas_calib"
            )
            
            if canvas_calib.json_data is not None:
                objects = canvas_calib.json_data["objects"]
                if len(objects) > 0:
                    last_obj = objects[-1]
                    # Cálculo seguro de distancia
                    dx = last_obj["width"] * last_obj["scaleX"]
                    dy = last_obj["height"] * last_obj["scaleY"]
                    dist_px = math.sqrt(dx**2 + dy**2)
                    
                    col1, col2 = st.columns([2,1])
                    with col1:
                        st.write(f"Longitud: **{dist_px:.1f} px**")
                    with col2:
                        metros_reales = st.number_input("Metros reales:", value=1.0, min_value=0.1)
                    
                    if st.button("✅ Aplicar Calibración"):
                        st.session_state['scale_px_per_meter'] = dist_px / metros_reales
                        st.success(f"Escala: {st.session_state['scale_px_per_meter']:.2f} px/m")
                        st.rerun()

        # --- MODO SEMBRADO ---
        elif modo == "📍 Sembrar Equipos":
            st.success(f"Colocando: **{tipo_equipo}**")
            
            canvas_sembrado = st_canvas(
                fill_color=canvas_fill_color,
                stroke_width=2,
                stroke_color=color_hex,
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="point",
                point_display_radius=radio_px_pantalla,
                display_toolbar=True, # Agregado Zoom
                key=f"canvas_{tipo_equipo}_{st.session_state['scale_px_per_meter']}"
            )
            
            if canvas_sembrado.json_data is not None:
                objects = canvas_sembrado.json_data["objects"]
                
                if len(objects) > 0:
                    st.write("### Vista Previa")
                    
                    # Generar imagen final con Matplotlib
                    fig, ax = plt.subplots(figsize=(10, 10 * img.height / img.width))
                    ax.imshow(img)
                    ax.axis('off')

                    conteo = 0
                    for obj in objects:
                        conteo += 1
                        x, y = obj["left"], obj["top"]
                        
                        circ = patches.Circle((x, y), radio_px_pantalla, 
                                            linewidth=2, 
                                            edgecolor=color_hex, 
                                            facecolor=color_hex,
                                            alpha=0.3)
                        ax.add_patch(circ)
                        center = patches.Circle((x, y), 5, color="white")
                        ax.add_patch(center)

                    st.markdown(f"**Equipos sembrados:** {conteo}")

                    buf = io.BytesIO()
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
                    st.download_button(
                        label="📥 Descargar Propuesta (PNG)",
                        data=buf.getvalue(),
                        file_name=f"Propuesta_{tipo_equipo}.png",
                        mime="image/png"
                    )

else:
    st.info("👆 Sube un plano para comenzar.")
