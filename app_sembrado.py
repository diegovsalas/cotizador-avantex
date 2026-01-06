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
    /* Estilo para la lista de sugerencias de IA */
    .sugerencia-ia {
        padding: 10px;
        background-color: #f0f2f6;
        border-left: 5px solid #FF8C00;
        margin-bottom: 10px;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado Inteligente (Modo Copiloto)")

# --- ESTADO ---
if 'puntos' not in st.session_state: st.session_state['puntos'] = []
if 'scale_px_per_meter' not in st.session_state: st.session_state['scale_px_per_meter'] = 35.0
if 'base_image' not in st.session_state: st.session_state['base_image'] = None
if 'file_id' not in st.session_state: st.session_state['file_id'] = ""
if 'analisis_ia' not in st.session_state: st.session_state['analisis_ia'] = ""
if 'sugerencias_puntos' not in st.session_state: st.session_state['sugerencias_puntos'] = ""

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
    tipo = st.selectbox("Modelo a colocar", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
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

    if col2.button("🗑️ Borrar Todo"):
        st.session_state['puntos'] = []
        st.session_state['analisis_ia'] = ""
        st.session_state['sugerencias_puntos'] = ""
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
    
    if st.button("✨ Analizar y Sugerir Puntos"):
        if not api_key:
            st.error("⚠️ Falta la API Key")
        elif not st.session_state['base_image']:
            st.warning("⚠️ Primero sube un plano")
        else:
            try:
                with st.spinner("Gemini está analizando el plano..."):
                    genai.configure(api_key=api_key)
                    # Usamos el alias universal estable
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    # --- PROMPT MEJORADO PARA PEDIR INSTRUCCIONES VISUALES ---
                    prompt = """
                    Actúa como un experto consultor en Marketing Olfativo de Aromatex.
                    Analiza el plano arquitectónico adjunto.

                    TAREA 1: ANÁLISIS ESTRATÉGICO (Breve)
                    - Tipo de espacio y objetivo olfativo principal.

                    TAREA 2: LISTA DE SEMBRADO SUGERIDO
                    - Proporciona una lista de 3 a 5 puntos EXACTOS donde sugieres colocar equipos.
                    - Para cada punto, dame una descripción VISUAL muy clara de dónde debo hacer clic en el mapa.
                    - Usa este formato exacto para la lista:
                    📍 PUNTO [Número]: [Descripción visual clara de la ubicación] - [Justificación breve]

                    Ejemplo:
                    📍 PUNTO 1: En el centro del acceso principal, justo al cruzar la reja. - Para captar tráfico de entrada.
                    """
                    
                    response = model.generate_content([prompt, st.session_state['base_image']])
                    full_text = response.text

                    # Separamos el análisis general de los puntos sugeridos (truco simple)
                    parts = full_text.split("TAREA 2: LISTA DE SEMBRADO SUGERIDO")
                    
                    st.session_state['analisis_ia'] = parts[0] if len(parts) > 0 else full_text
                    st.session_state['sugerencias_puntos'] = parts[1] if len(parts) > 1 else "No se generaron puntos específicos."
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error de conexión: {e}")

# --- APP PRINCIPAL ---
uploaded_file = st.file_uploader("Sube plano (PDF, JPG)", type=["pdf", "jpg", "png"])

if uploaded_file:
    fid = f"{uploaded_file.name}-{uploaded_file.size}"
    if st.session_state['file_id'] != fid:
        st.session_state['base_image'] = process_file(uploaded_file)
        st.session_state['file_id'] = fid
        st.session_state['puntos'] = [] 
        st.session_state['analisis_ia'] = ""
        st.session_state['sugerencias_puntos'] = ""
        st.rerun()

if st.session_state['base_image']:
    
    # --- DISEÑO DE DOS COLUMNAS ---
    col_ia, col_mapa = st.columns([1, 2])

    # --- COLUMNA IZQUIERDA: SUGERENCIAS DE LA IA ---
    with col_ia:
        st.subheader("🧠 Sugerencias de la IA")
        if st.session_state['sugerencias_puntos']:
            st.info("Lee las sugerencias y haz clic en el mapa para 'palomearlas'.")
            
            # Limpiamos y mostramos las sugerencias como una lista visual
            sugerencias = st.session_state['sugerencias_puntos'].strip().split('\n')
            for linea in sugerencias:
                if "📍" in linea:
                    st.markdown(f"""<div class="sugerencia-ia">{linea}</div>""", unsafe_allow_html=True)
            
            with st.expander("Ver Análisis Estratégico Completo"):
                 st.markdown(st.session_state['analisis_ia'])
        else:
            st.write("Presiona '✨ Analizar y Sugerir Puntos' en la barra lateral para recibir instrucciones de sembrado.")
            st.metric("Equipos Colocados por ti", len(st.session_state['puntos']))

    # --- COLUMNA DERECHA: EL MAPA INTERACTIVO ---
    with col_mapa:
        st.subheader("📍 Tu Sembrado (Haz Clic)")
        
        # VISUALIZADOR
        display_img = st.session_state['base_image'].copy()
        draw = ImageDraw.Draw(display_img, "RGBA")
        
        for p in st.session_state['puntos']:
            x, y = p['x'], p['y']
            r = p['radio']
            draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=3)
            draw.ellipse((x-5, y-5, x+5, y+5), fill="white", outline="black")
        
        # COMPONENTE DE CLIC
        value = streamlit_image_coordinates(
            display_img,
            key="sembrado_click",
            width=700 # Hacemos el mapa un poco más grande
        )
        
        if value is not None:
            new_point = {"x": value["x"], "y": value["y"], "color": color, "radio": radio_px}
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != new_point['x']:
                st.session_state['puntos'].append(new_point)
                st.rerun()

    # 3. EXPORTAR
    if st.session_state['puntos']:
        st.divider()
        if st.button("📸 Generar Imagen Final de Propuesta"):
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
