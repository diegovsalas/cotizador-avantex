import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai 
from streamlit_image_coordinates import streamlit_image_coordinates

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex + IA", layout="wide", page_icon="🧠")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Inteligente con Gemini")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = ""

# --- PROCESAMIENTO ---
def process_file(uploaded_file):
    try:
        image = None
        uploaded_file.seek(0)
        
        # PDF a Imagen
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # APLANAR A BLANCO
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

        # Redimensionar
        MAX_WIDTH = 1000
        if image.width > MAX_WIDTH:
            ratio = MAX_WIDTH / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((MAX_WIDTH, h), Image.Resampling.LANCZOS)
            
        return image
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Configuración")
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
    st.caption(f"Radio cobertura: {radio_px} px")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    if col1.button("↩️ Deshacer"):
        if st.session_state['puntos']:
            st.session_state['puntos'].pop()
            st.rerun()

    if col2.button("🗑️ Borrar"):
        st.session_state['puntos'] = []
        st.session_state['analisis_ia'] = ""
        st.rerun()
        
    st.divider()
    scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()

    # --- SECCIÓN INTELIGENCIA ARTIFICIAL ---
    st.divider()
    st.header("🧠 Consultor IA")
    
    api_key = st.text_input("Google API Key:", type="password")
    
    # BOTÓN DE DIAGNÓSTICO
    if api_key:
        if st.expander("🔍 Ver modelos disponibles (Debug)"):
            try:
                genai.configure(api_key=api_key)
                st.write("Tu API Key tiene acceso a:")
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        st.code(m.name)
            except Exception as e:
                st.error(f"Error de llave: {e}")

    if st.button("✨ Analizar Plano con Gemini"):
        if not api_key:
            st.error("⚠️ Falta la API Key")
        elif not st.session_state['base_image']:
            st.warning("⚠️ Primero sube un plano")
        else:
            try:
                with st.spinner("Conectando con Google Gemini..."):
                    genai.configure(api_key=api_key)
                    
                    # INTENTO 1: Modelo Flash Latest (Suele funcionar)
                    nombre_modelo = 'gemini-1.5-flash-latest'
                    
                    # Configuración básica
                    model = genai.GenerativeModel(nombre_modelo)
                    
                    prompt = """
                    Actúa como un experto consultor en Marketing Olfativo para la empresa Aromatex.
                    Analiza este plano arquitectónico adjunto.
                    1. Identificar el tipo de inmueble.
                    2. Detectar las zonas principales (Recepción, Sala, Baños).
                    3. Recomendar estratégicamente DÓNDE colocar los difusores.
                    Responde en español, formato lista.
                    """
                    
                    response = model.generate_content([prompt, st.session_state['base_image']])
                    st.session_state['analisis_ia'] = response.text
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error con el modelo '{nombre_modelo}': {e}")
                st.info("💡 Consejo: Abre la sección '🔍 Ver modelos disponibles' arriba y busca un nombre que empiece con 'models/gemini...'.")

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = [] 
        st.session_state['analisis_ia'] = ""
        st.rerun()

if st.session_state['base_image']:
    
    # 1. RESULTADO IA
    if st.session_state['analisis_ia']:
        st.success("✅ Análisis de IA Completado")
        with st.expander("📄 Ver Reporte de Gemini", expanded=True):
            st.markdown(st.session_state['analisis_ia'])
        st.divider()

    # 2. VISUALIZADOR
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=3)
        draw.ellipse((x-5, y-5, x+5, y+5), fill="white", outline="black")

    st.write("### 📍 Haz clic en el mapa para colocar equipos")
    
    value = streamlit_image_coordinates(
        display_img,
        key="sembrado_click"
    )
    
    if value is not None:
        new_point = {"x": value["x"], "y": value["y"], "color": color, "radio": radio_px}
        if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != new_point['x']:
            st.session_state['puntos'].append(new_point)
            st.rerun()

    # 3. EXPORTAR
    if st.session_state['puntos']:
        st.divider()
        st.metric("Equipos Colocados", len(st.session_state['puntos']))
        
        if st.button("📸 Generar Imagen Final"):
            buf = io.BytesIO()
            fig, ax = plt.subplots(figsize=(10, 10 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
            st.download_button("📥 Descargar Propuesta PNG", buf.getvalue(), "propuesta_sembrado.png", "image/png")

else:
    st.info("👆 Sube un plano para comenzar.")
