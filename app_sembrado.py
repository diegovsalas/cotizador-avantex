import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="🌱")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    h1 {color: #2E8B57;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Inteligente")

# --- GESTIÓN DE ESTADO (SESSION STATE) ---
if 'scale_px_per_meter' not in st.session_state:
    st.session_state['scale_px_per_meter'] = 35.0 
if 'bg_image' not in st.session_state:
    st.session_state['bg_image'] = None
if 'original_file_name' not in st.session_state:
    st.session_state['original_file_name'] = ""

# --- FUNCIONES AUXILIARES ---
def load_image(uploaded_file):
    if uploaded_file.name != st.session_state['original_file_name']:
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
        else:
            image = Image.open(uploaded_file)
        
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
    
    # --- CORRECCIÓN DE COLORES ---
    # Usamos Hexadecimal simple para evitar errores en Matplotlib
    if "Home" in tipo_equipo:
        radio_real = 5.6
        color_hex = "#2E8B57" # Verde SeaGreen
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color_hex = "#FF8C00" # Naranja DarkOrange
    else:
        radio_real = 16.0
        color_hex = "#DC143C" # Rojo Crimson

    # Definimos colores derivados
    # "44" al final de un hex añade transparencia (alpha ~25%)
    canvas_fill_color = color_hex + "44"  

    st.divider()
    modo = st.radio("Modo de trabajo:", ["📏 Calibrar Escala", "📍 Sembrar Equipos"], index=1)
    
    st.divider()
    st.metric("Escala Actual", f"{st.session_state['scale_px_per_meter']:.1f} px/m")
    
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
            st.info("💡 Dibuja una línea sobre una medida conocida (ej. puerta) y escribe su longitud real.")
            
            canvas_calib = st_canvas(
                fill_color="rgba(0, 0, 0, 0)",
                stroke_width=3,
                stroke_color="#0000FF",
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="line",
                key="canvas_calib"
            )
            
            if canvas_calib.json_data is not None:
                objects = canvas_calib.json_data["objects"]
                if len(objects) > 0:
                    last_obj = objects[-1]
                    x1, y1 = last_obj["left"], last_obj["top"]
                    x2 = x1 + (last_obj["width"] * last_obj["scaleX"])
                    y2 = y1 + (last_obj["height"] * last_obj["scaleY"])
                    
                    dist_px = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                    
                    col1, col2 = st.columns([2,1])
                    with col1:
                        st.write(f"Longitud dibujada: **{dist_px:.1f} píxeles**")
                    with col2:
                        metros_reales = st.number_input("Metros reales:", value=1.0, min_value=0.1, step=0.5)
                    
                    if st.button("✅ Aplicar Calibración"):
                        nueva_escala = dist_px / metros_reales
                        st.session_state['scale_px_per_meter'] = nueva_escala
                        st.success(f"Escala calibrada a {nueva_escala:.2f} px/m")
                        st.rerun()

        # --- MODO SEMBRADO ---
        elif modo == "📍 Sembrar Equipos":
            st.success(f"Colocando: **{tipo_equipo}**")
            
            canvas_sembrado = st_canvas(
                fill_color=canvas_fill_color, # Usamos el Hex con transparencia
                stroke_width=2,
                stroke_color=color_hex,
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="point",
                point_display_radius=radio_px_pantalla, 
                key=f"canvas_sembrado_{tipo_equipo}_{st.session_state['scale_px_per_meter']}"
            )
            
            if canvas_sembrado.json_data is not None:
                objects = canvas_sembrado.json_data["objects"]
                
                if len(objects) > 0:
                    st.write("### Vista Previa")
                    
                    # Generar imagen final
                    fig, ax = plt.subplots(figsize=(12, 12 * img.height / img.width))
                    ax.imshow(img)
                    ax.axis('off')

                    conteo = 0
                    for obj in objects:
                        conteo += 1
                        x, y = obj["left"], obj["top"]
                        
                        # CORRECCIÓN AQUÍ: Usamos color_hex y alpha separado
                        circ = patches.Circle((x, y), radio_px_pantalla, 
                                            linewidth=2, 
                                            edgecolor=color_hex, 
                                            facecolor=color_hex,
                                            alpha=0.3) # Transparencia controlada por Matplotlib
                        ax.add_patch(circ)
                        
                        center = patches.Circle((x, y), 5, color="white")
                        ax.add_patch(center)

                    st.markdown(f"**Equipos sembrados:** {conteo}")

                    buf = io.BytesIO()
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
                    buf.seek(0)
                    
                    st.download_button(
                        label="📥 Descargar Propuesta (PNG)",
                        data=buf,
                        file_name=f"Propuesta_Aromatex_{tipo_equipo}.png",
                        mime="image/png"
                    )

else:
    st.info("👆 Sube un plano para comenzar.")
