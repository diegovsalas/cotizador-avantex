import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai 
from streamlit_image_coordinates import streamlit_image_coordinates
import math

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sembrado Aromatex + IA", layout="wide", page_icon="🧬")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .sugerencia-box {
        background-color: #f0f2f6;
        border-left: 5px solid #6366f1;
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 5px;
    }
    iframe {border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Profesional V34")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = ""
if 'sugerencias_puntos' not in st.session_state: st.session_state['sugerencias_puntos'] = ""
if 'calibracion_clicks' not in st.session_state: st.session_state['calibracion_clicks'] = []

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

        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

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
    
    # --- GESTIÓN INTELIGENTE DE API KEY ---
    api_key = None
    
    # 1. Intentamos leer de los secretos (automático)
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("🔑 API Key cargada automáticamente")
    else:
        # 2. Si no existe, pedimos manual
        with st.expander("🔑 Configuración IA", expanded=True):
            api_key = st.text_input("Google API Key:", type="password")
            st.caption("Consejo: Crea .streamlit/secrets.toml para no escribirla siempre.")

    st.divider()

    st.subheader("Modo de Trabajo")
    modo = st.radio("Herramienta:", ["📍 Sembrar Equipos", "📏 Calibrar Escala"], index=0)

    st.divider()

    if modo == "📍 Sembrar Equipos":
        tipo = st.selectbox("Modelo", ["Advance Pro (100 m²)", "Plus Pro (300 m²)", "Extreme (800 m²)"])
        if "Advane" in tipo:
            color = "#2E8B57"
            radio_real = 5.6
        elif "Plus" in tipo:
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
        if col2.button("🗑️ Borrar Puntos"):
            st.session_state['puntos'] = []
            st.rerun()

    else: # MODO CALIBRAR
        st.info("Clic A (Inicio) -> Clic B (Fin)")
        
        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            
            st.write(f"📏 Medida: **{dist_px:.1f} px**")
            metros = st.number_input("Metros reales:", value=0.90, step=0.10)
            
            if st.button("✅ Aplicar Escala"):
                if metros > 0:
                    st.session_state['scale_px_per_meter'] = dist_px / metros
                    st.session_state['calibracion_clicks'] = []
                    st.success("Escala ajustada.")
                    st.rerun()
        
        if st.button("❌ Reiniciar Medición"):
            st.session_state['calibracion_clicks'] = []
            st.rerun()

    st.divider()
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

    # --- ZONA IA (SOLO VISIBLE EN MODO SEMBRADO Y SI HAY KEY) ---
    if api_key and modo == "📍 Sembrar Equipos":
        col_btn, col_txt = st.columns([1, 4])
        with col_btn:
            if st.button("✨ Preguntar a Gemini"):
                try:
                    with st.spinner("Analizando plano..."):
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        prompt = """
                        Actúa como experto en Marketing Olfativo. Analiza el plano visualmente.
                        TAREA: Dame una lista de 3 puntos estratégicos para colocar difusores.
                        FORMATO: "📍 **[Zona]**: [Instrucción visual breve]"
                        """
                        response = model.generate_content([prompt, st.session_state['base_image']])
                        st.session_state['sugerencias_puntos'] = response.text
                        st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")
        
        with col_txt:
            if st.session_state['sugerencias_puntos']:
                with st.expander("💡 Ver Sugerencias de Gemini", expanded=True):
                    st.markdown(st.session_state['sugerencias_puntos'])

    # --- VISUALIZADOR ---
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # DIBUJAR PUNTOS
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=4)
        draw.ellipse((x-6, y-6, x+6, y+6), fill="white", outline="black")
        draw.ellipse((x-3, y-3, x+3, y+3), fill=p['color'])

    # DIBUJAR CALIBRACIÓN
    clicks = st.session_state['calibracion_clicks']
    if len(clicks) > 0:
        p1 = clicks[0]
        draw.ellipse((p1['x']-5, p1['y']-5, p1['x']+5, p1['y']+5), fill="blue", outline="white")
        if len(clicks) == 2:
            p2 = clicks[1]
            draw.ellipse((p2['x']-5, p2['y']-5, p2['x']+5, p2['y']+5), fill="blue", outline="white")
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="blue", width=3)

    if modo == "📍 Sembrar Equipos":
        st.write(f"📍 **Modo Sembrado** | Equipos: {len(st.session_state['puntos'])}")
    else:
        st.info("📏 **Modo Calibración** | Haz clic en dos puntos para medir.")

    value = streamlit_image_coordinates(display_img, key="clicker")
    
    if value is not None:
        x, y = value["x"], value["y"]
        
        if modo == "📍 Sembrar Equipos":
            new_point = {"x": x, "y": y, "color": color, "radio": radio_px}
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != x:
                st.session_state['puntos'].append(new_point)
                st.rerun()
                
        elif modo == "📏 Calibrar Escala":
            if len(st.session_state['calibracion_clicks']) < 2:
                if not st.session_state['calibracion_clicks'] or st.session_state['calibracion_clicks'][-1]['x'] != x:
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        if st.button("📸 Descargar Propuesta"):
            buf = io.BytesIO()
            fig, ax = plt.subplots(figsize=(12, 12 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
            st.download_button("Bajar Imagen PNG", buf.getvalue(), "sembrado.png", "image/png")
