import streamlit as st
from PIL import Image, ImageDraw
import io
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import google.generativeai as genai 
from streamlit_image_coordinates import streamlit_image_coordinates

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sembrado Aromatex", layout="wide", page_icon="📍")

# CSS para mejorar la UX visual
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .stAlert {padding: 0.5rem;}
    /* Hacemos que el mapa destaque */
    iframe {border: 1px solid #ddd; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado (Modo Copiloto)")

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
        
        if uploaded_file.type == "application/pdf":
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            # Aumentamos calidad para que se vea bien en grande (Zoom 2.0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=True)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
        else:
            image = Image.open(uploaded_file)

        # APLANAR A BLANCO (Vital para ver líneas negras)
        image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, image).convert("RGB")

        # Redimensionar inteligente (Ancho fijo grande para buena UX)
        target_width = 1200 # Más grande para ver detalles
        if image.width > target_width:
            ratio = target_width / float(image.width)
            h = int(float(image.height) * float(ratio))
            image = image.resize((target_width, h), Image.Resampling.LANCZOS)
            
        return image
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return None

# --- SIDEBAR (CONTROLES) ---
with st.sidebar:
    st.header("⚙️ Controles")
    
    # 1. API KEY
    with st.expander("🔑 Configuración IA", expanded=True):
        api_key = st.text_input("Google API Key:", type="password")

    st.divider()

    # 2. EQUIPOS
    tipo = st.selectbox("Modelo a colocar", ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
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
    st.caption(f"Radio visual: {radio_px} px")
    
    # 3. ESCALA
    scale = st.number_input("Escala (Px/m):", value=float(st.session_state['scale_px_per_meter']), step=0.1)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()

    st.divider()
    
    # 4. ACCIONES
    col_a, col_b = st.columns(2)
    if col_a.button("↩️ Deshacer"):
        if st.session_state['puntos']:
            st.session_state['puntos'].pop()
            st.rerun()

    if col_b.button("🗑️ Borrar"):
        st.session_state['puntos'] = []
        st.session_state['analisis_ia'] = ""
        st.session_state['sugerencias_puntos'] = ""
        st.rerun()

# --- ÁREA PRINCIPAL ---

# 1. CARGA DE ARCHIVO
if not st.session_state['base_image']:
    uploaded_file = st.file_uploader("📂 Sube tu plano (PDF o Imagen)", type=["pdf", "jpg", "png"])
    if uploaded_file:
        fid = f"{uploaded_file.name}-{uploaded_file.size}"
        if st.session_state['file_id'] != fid:
            with st.spinner("Procesando imagen de alta calidad..."):
                st.session_state['base_image'] = process_file(uploaded_file)
                st.session_state['file_id'] = fid
                st.session_state['puntos'] = [] 
                st.session_state['analisis_ia'] = ""
                st.session_state['sugerencias_puntos'] = ""
                st.rerun()

# 2. INTERFAZ DE TRABAJO
if st.session_state['base_image']:
    
    # --- SECCIÓN A: ANÁLISIS IA (Arriba, para no comprimir el mapa) ---
    if api_key:
        col_btn, col_info = st.columns([1, 4])
        with col_btn:
            if st.button("✨ Analizar Plano"):
                try:
                    with st.spinner("Gemini analizando zonas estratégicas..."):
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        
                        prompt = """
                        Actúa como experto en Marketing Olfativo. Analiza el plano visualmente.
                        
                        TAREA 1: RESUMEN (Máximo 50 palabras)
                        - Tipo de espacio y objetivo principal.
                        
                        TAREA 2: PUNTOS SUGERIDOS
                        - Lista 3 a 5 puntos estratégicos.
                        - Formato: "📍 **[Ubicación]**: [Razón breve]"
                        """
                        
                        response = model.generate_content([prompt, st.session_state['base_image']])
                        full_text = response.text
                        parts = full_text.split("TAREA 2: PUNTOS SUGERIDOS")
                        
                        st.session_state['analisis_ia'] = parts[0]
                        st.session_state['sugerencias_puntos'] = parts[1] if len(parts) > 1 else full_text
                        st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")
        
        with col_info:
            # Mostramos sugerencias en una caja limpia
            if st.session_state['sugerencias_puntos']:
                st.success("💡 Sugerencias de Sembrado (Haz clic en el mapa para aplicarlas)")
                st.markdown(st.session_state['sugerencias_puntos'])
                with st.expander("Ver análisis detallado"):
                    st.write(st.session_state['analisis_ia'])

    # --- SECCIÓN B: MAPA INTERACTIVO (Grande y Limpio) ---
    st.divider()
    
    # Preparar imagen para visualizar (UX MEJORADA: SOLO CONTORNOS)
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        c_color = p['color']
        
        # UX TRICK: Dibujamos solo el ANILLO (outline) y no el relleno.
        # Así el usuario puede ver el plano debajo del círculo.
        draw.ellipse((x-r, y-r, x+r, y+r), outline=c_color, width=4)
        
        # Punto central sólido para precisión
        draw.ellipse((x-6, y-6, x+6, y+6), fill="white", outline="black")
        draw.ellipse((x-3, y-3, x+3, y+3), fill=c_color)

    st.write(f"📍 **Haz clic en el plano** | Equipos colocados: {len(st.session_state['puntos'])}")
    
    # El componente de coordenadas
    # width=None hace que use todo el ancho de la columna/pantalla
    value = streamlit_image_coordinates(
        display_img,
        key="sembrado_click"
    )
    
    if value is not None:
        new_point = {"x": value["x"], "y": value["y"], "color": color, "radio": radio_px}
        # Evitar duplicados
        if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != new_point['x']:
            st.session_state['puntos'].append(new_point)
            st.rerun()

    # --- SECCIÓN C: DESCARGA ---
    if st.session_state['puntos']:
        st.divider()
        if st.button("📸 Descargar Propuesta Final (Con Transparencias)"):
            buf = io.BytesIO()
            # AQUÍ SI usamos Matplotlib para hacer el relleno bonito y transparente
            fig, ax = plt.subplots(figsize=(12, 12 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                # En la exportación SÍ ponemos relleno con alpha
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                # Y el contorno
                c_outline = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], fill=False, linewidth=2)
                ax.add_patch(c_outline)
                # Y el centro
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
            st.download_button("📥 Bajar Imagen PNG", buf.getvalue(), "propuesta_sembrado.png", "image/png", type="primary")
