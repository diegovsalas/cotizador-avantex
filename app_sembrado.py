import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import math
import uuid

# --- 1. CONFIGURACIÓN BÁSICA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Configuración Inicial (Estable)")

# --- 2. VARIABLES DE ESTADO ---
if 'bg_image' not in st.session_state: st.session_state['bg_image'] = None
if 'canvas_key' not in st.session_state: st.session_state['canvas_key'] = str(uuid.uuid4())
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0

# --- 3. FUNCIONES DE PROCESAMIENTO ---
def load_and_process_file(uploaded_file):
    try:
        image = None
        
        # A) Si es PDF
        if uploaded_file.type == "application/pdf":
            # Leemos el PDF con PyMuPDF
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x para buena calidad sin exagerar
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        
        # B) Si es Imagen (JPG/PNG)
        else:
            image = Image.open(uploaded_file)
            
        # --- CORRECCIÓN DE FONDO NEGRO (Vital) ---
        # Convertimos a RGBA para manejar transparencias
        image = image.convert("RGBA")
        # Creamos un fondo blanco puro
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        # Pegamos la imagen sobre el blanco (alpha_composite mezcla bien las transparencias)
        combined = Image.alpha_composite(background, image)
        # Convertimos finalmente a RGB simple
        image = combined.convert("RGB")
        
        # --- REDIMENSIONADO DE SEGURIDAD ---
        # Si la imagen es gigante (>1000px), el navegador la bloquea. La ajustamos.
        MAX_WIDTH = 1000
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(image.width)
            new_height = int(float(image.height) * float(ratio))
            image = image.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)
            
        return image
        
    except Exception as e:
        st.error(f"Error cargando archivo: {e}")
        return None

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("Configuración")
    
    # Selección de equipo
    tipo_equipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
    # Definir colores y radios
    if "Home" in tipo_equipo:
        radio_real = 5.6
        color = "#2E8B57" # Verde
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color = "#FF8C00" # Naranja
    else:
        radio_real = 16.0
        color = "#DC143C" # Rojo
        
    st.divider()
    modo = st.radio("Herramienta", ["📏 Calibrar Escala", "📍 Sembrar Equipos"])
    
    st.divider()
    # Escala Manual
    new_scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if new_scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = new_scale
        st.rerun()
        
    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio visual: {radio_px} px")

    if st.button("🗑️ Limpiar Todo"):
        st.session_state['bg_image'] = None
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

# --- 5. ÁREA PRINCIPAL ---
uploaded_file = st.file_uploader("Sube tu plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

# Lógica de carga: Solo procesamos si hay archivo y no está cargado aún
if uploaded_file:
    # Usamos un ID simple para saber si cambió el archivo
    file_id = f"{uploaded_file.name}-{uploaded_file.size}"
    
    if 'last_file_id' not in st.session_state or st.session_state['last_file_id'] != file_id:
        st.session_state['bg_image'] = load_and_process_file(uploaded_file)
        st.session_state['last_file_id'] = file_id
        # Forzamos una clave nueva para que el canvas se reinicie por completo
        st.session_state['canvas_key'] = str(uuid.uuid4())
        st.rerun()

# Mostrar Editor
if st.session_state['bg_image']:
    img = st.session_state['bg_image']
    
    st.write("### Editor de Sembrado")
    st.caption("Usa el mouse para marcar puntos o líneas.")
    
    # EL CANVAS
    # stroke_color y fill_color definen cómo se ven los puntos
    canvas_result = st_canvas(
        fill_color=color + "55",  # Color con transparencia hex (aprox 30%)
        stroke_width=2,
        stroke_color=color,
        background_image=img,
        update_streamlit=True,
        height=img.height,
        width=img.width,
        drawing_mode="point" if modo == "📍 Sembrar Equipos" else "line",
        point_display_radius=radio_px,
        display_toolbar=True, # Muestra la barra de herramientas (Zoom, Pan, Basura)
        key=st.session_state['canvas_key']
    )
    
    # LÓGICA DE RESULTADOS
    if canvas_result.json_data and "objects" in canvas_result.json_data:
        objects = canvas_result.json_data["objects"]
        n_objects = len(objects)
        
        if n_objects > 0:
            # A) Lógica de Calibración
            if modo == "📏 Calibrar Escala":
                try:
                    obj = objects[-1] # Último objeto dibujado
                    # Distancia Pitágoras
                    dx = obj["width"] * obj["scaleX"]
                    dy = obj["height"] * obj["scaleY"]
                    dist_px = math.sqrt(dx**2 + dy**2)
                    
                    st.info(f"Longitud trazada: {dist_px:.1f} px")
                    metros = st.number_input("¿A cuántos metros equivale?", value=1.0)
                    
                    if st.button("Guardar Nueva Escala"):
                        st.session_state['scale_px_per_meter'] = dist_px / metros
                        st.success(f"Escala actualizada: {st.session_state['scale_px_per_meter']:.2f} px/m")
                        # Recargamos para que los radios de los puntos se actualicen
                        st.rerun()
                except:
                    pass

            # B) Lógica de Sembrado
            elif modo == "📍 Sembrar Equipos":
                st.metric("Equipos Sembrados", n_objects)
                
                # Botón de Descarga
                if st.button("📸 Descargar Imagen Final"):
                    buf = io.BytesIO()
                    
                    # Usamos Matplotlib para generar la imagen de alta calidad
                    fig, ax = plt.subplots(figsize=(10, 10 * img.height / img.width))
                    ax.imshow(img)
                    ax.axis('off')
                    
                    for o in objects:
                        # Coordenadas y Radio
                        x, y = o["left"], o["top"]
                        # Dibujamos el área de cobertura
                        circle = patches.Circle((x, y), radio_px, color=color, alpha=0.3)
                        ax.add_patch(circle)
                        # Dibujamos el punto central
                        center = patches.Circle((x, y), 5, color='white')
                        ax.add_patch(center)
                    
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
                    st.download_button(
                        label="📥 Bajar Imagen",
                        data=buf.getvalue(),
                        file_name="propuesta_sembrado.png",
                        mime="image/png"
                    )

else:
    st.info("👆 Sube un plano para comenzar.")
