import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai 
from streamlit_image_coordinates import streamlit_image_coordinates
import math

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="📏")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    iframe {border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado de Precisión")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'calibracion_clicks' not in st.session_state: st.session_state['calibracion_clicks'] = [] # Para guardar los 2 clics de medir

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        image = None
        uploaded_file.seek(0)
        
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # APLANAR A BLANCO
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

        # Redimensionar (Ancho fijo grande)
        target_width = 1000
        if image.width > target_width:
            ratio = target_width / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((target_width, h), Image.Resampling.LANCZOS)
            
        return image
    except Exception as e:
        st.error(f"Error: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Panel de Control")
    
    # 1. MODO DE TRABAJO
    modo = st.radio("¿Qué quieres hacer?", ["📍 Sembrar Equipos", "📏 Calibrar Escala"], index=0)
    
    st.divider()

    if modo == "📍 Sembrar Equipos":
        st.subheader("Configuración de Equipos")
        tipo = st.selectbox("Modelo", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
        
        if "Home" in tipo:
            color = "#2E8B57"
            radio_real = 5.6
        elif "Advance" in tipo:
            color = "#FF8C00"
            radio_real = 9.7
        else:
            color = "#DC143C"
            radio_real = 16.0
            
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        st.caption(f"Radio visual: {radio_px} px")
        
        col1, col2 = st.columns(2)
        if col1.button("↩️ Deshacer"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if col2.button("🗑️ Borrar Todo"):
            st.session_state['puntos'] = []
            st.rerun()

    else: # MODO CALIBRAR
        st.subheader("Herramienta de Medición")
        st.info("Haz clic en el PUNTO A (inicio) y luego en el PUNTO B (fin) de una medida conocida (ej. una puerta).")
        
        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            
            # Calcular distancia en píxeles (Pitágoras)
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            
            st.write(f"📏 Distancia en pantalla: **{dist_px:.1f} px**")
            
            metros_reales = st.number_input("¿Cuántos metros son en la realidad?", value=0.90, step=0.10)
            
            if st.button("✅ Calcular y Aplicar Escala"):
                if metros_reales > 0:
                    nueva_escala = dist_px / metros_reales
                    st.session_state['scale_px_per_meter'] = nueva_escala
                    st.session_state['calibracion_clicks'] = [] # Reiniciar
                    st.success(f"¡Nueva escala guardada! {nueva_escala:.2f} Px/m")
                    st.rerun()
        
        if st.button("❌ Cancelar Medición"):
            st.session_state['calibracion_clicks'] = []
            st.rerun()

    st.divider()
    # Mostrar escala actual (editable manualmente también)
    scale = st.number_input("Escala Actual (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        with st.spinner("Procesando..."):
            st.session_state['base_image'] = process_file(uploaded_file)
            st.session_state['file_id'] = fid
            st.session_state['puntos'] = [] 
            st.session_state['calibracion_clicks'] = []
            st.rerun()

if st.session_state['base_image']:
    
    # PREPARAR IMAGEN DE VISUALIZACIÓN
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # A) DIBUJAR PUNTOS DE SEMBRADO (Si existen)
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        # Anillo
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=3)
        # Centro
        draw.ellipse((x-5, y-5, x+5, y+5), fill="white", outline="black")

    # B) DIBUJAR LÍNEA DE CALIBRACIÓN (Si estamos midiendo)
    clicks = st.session_state['calibracion_clicks']
    if len(clicks) > 0:
        # Dibujar primer punto
        p1 = clicks[0]
        draw.ellipse((p1['x']-5, p1['y']-5, p1['x']+5, p1['y']+5), fill="blue", outline="white")
        
        if len(clicks) == 2:
            # Dibujar línea completa
            p2 = clicks[1]
            draw.ellipse((p2['x']-5, p2['y']-5, p2['x']+5, p2['y']+5), fill="blue", outline="white")
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="blue", width=3)

    # --- COMPONENTE INTERACTIVO ---
    if modo == "📍 Sembrar Equipos":
        st.write("📍 **Modo Sembrado:** Haz clic para colocar equipos.")
    else:
        st.info("📏 **Modo Calibración:** Clic 1 (Inicio) -> Clic 2 (Fin) -> Ingresa Metros en la barra lateral.")

    value = streamlit_image_coordinates(
        display_img,
        key="clicker_principal"
    )
    
    # LÓGICA DE CLICS
    if value is not None:
        x, y = value["x"], value["y"]
        
        # Lógica para MODO SEMBRADO
        if modo == "📍 Sembrar Equipos":
            new_point = {"x": x, "y": y, "color": color, "radio": radio_px}
            # Evitar duplicados
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != x:
                st.session_state['puntos'].append(new_point)
                st.rerun()
                
        # Lógica para MODO CALIBRAR
        elif modo == "📏 Calibrar Escala":
            # Solo permitimos 2 clicks. Si ya hay 2, el usuario debe resetear o calcular.
            if len(st.session_state['calibracion_clicks']) < 2:
                # Evitar duplicado inmediato
                if not st.session_state['calibracion_clicks'] or st.session_state['calibracion_clicks'][-1]['x'] != x:
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    # --- DESCARGA FINAL ---
    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        if st.button("📸 Descargar Propuesta"):
            buf = io.BytesIO()
            fig, ax = plt.subplots(figsize=(10, 10 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
            st.download_button("Descargar PNG", buf.getvalue(), "propuesta.png", "image/png")
