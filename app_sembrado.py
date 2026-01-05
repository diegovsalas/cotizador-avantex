import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Importamos la librería de coordenadas (Más estable que el canvas)
from streamlit_image_coordinates import streamlit_image_coordinates

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado (Método Click)")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""

# --- PROCESAMIENTO (EL APLANADOR DE IMAGEN) ---
def process_file(uploaded_file):
    try:
        image = None
        uploaded_file.seek(0)
        
        # 1. Convertir PDF
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            # Zoom 1.5x
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # 2. FORZAR FONDO BLANCO (Crucial para ver el plano)
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        # Pegamos el plano sobre el blanco
        image = Image.alpha_composite(background, image).convert("RGB")

        # 3. Redimensionar (Evita lentitud)
        MAX_WIDTH = 1000
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        return image
    except Exception as e:
        st.error(f"Error: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    tipo = st.selectbox("Modelo", ["Home Pro", "Advance Pro", "Extreme"])
    
    if "Home" in tipo:
        color = "#2E8B57" # Verde
        radio_real = 5.6
    elif "Advance" in tipo:
        color = "#FF8C00" # Naranja
        radio_real = 9.7
    else:
        color = "#DC143C" # Rojo
        radio_real = 16.0
        
    radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio cobertura: {radio_px} px")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    if col1.button("↩️ Deshacer"):
        if st.session_state['puntos']:
            st.session_state['puntos'].pop()
            st.rerun()

    if col2.button("🗑️ Borrar"):
        st.session_state['puntos'] = []
        st.rerun()
        
    st.divider()
    scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()

# --- APP ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = [] 
        st.rerun()

if st.session_state['base_image']:
    # Copiamos la imagen base para pintar sobre ella
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # Pintamos los puntos existentes
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        # Simular transparencia dibujando contorno grueso y centro
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=3)
        draw.ellipse((x-5, y-5, x+5, y+5), fill="white", outline="black")

    st.write("### Haz clic para colocar equipos")
    
    # --- COMPONENTE DE CLIC ---
    value = streamlit_image_coordinates(
        display_img,
        key="sembrado_click"
    )
    
    # Detectar nuevo clic
    if value is not None:
        new_point = {"x": value["x"], "y": value["y"], "color": color, "radio": radio_px}
        
        # Evitar duplicados por refresco
        if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != new_point['x']:
            st.session_state['puntos'].append(new_point)
            st.rerun()

    # --- RESULTADOS ---
    if st.session_state['puntos']:
        st.metric("Equipos Colocados", len(st.session_state['puntos']))
        
        if st.button("📸 Descargar Imagen"):
            buf = io.BytesIO()
            # Usar Matplotlib para exportar con transparencia bonita
            fig, ax = plt.subplots(figsize=(10, 10 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
            st.download_button("Bajar PNG", buf.getvalue(), "sembrado.png", "image/png")

else:
    st.info("Sube un archivo.")
