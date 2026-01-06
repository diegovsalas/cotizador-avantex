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
st.set_page_config(page_title="Sembrado Aromatex + IA", layout="wide", page_icon="🧬")
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    .metrics-box {
        background-color: #e8fdf5;
        border: 1px solid #6366f1;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🌱 Aromatex: Sembrado de Precisión V38")

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
    st.header("⚙️ Configuración")
    
    # --- 1. DATOS DEL ESPACIO (NUEVO) ---
    with st.expander("📐 Datos del Espacio", expanded=True):
        area_total = st.number_input("Área Piso de Venta (m²):", value=100.0, step=10.0)
        altura = st.number_input("Altura Techo (m):", value=3.00, step=0.10)
        
        # Factor de ajuste por altura (Referencia 3.0m)
        factor_altura = 3.0 / altura if altura > 0 else 1.0
        if altura > 3.1:
            st.warning(f"⚠️ Techo alto ({altura}m). La cobertura se reduce un {100*(1-factor_altura):.0f}%.")

    st.divider()
    
    # --- 2. ESCALA ---
    st.subheader("🔍 Escala")
    col_p1, col_p2, col_p3 = st.columns(3)
    if col_p1.button("🛍️ Retail"):
        st.session_state['scale_px_per_meter'] = 55.0
        st.rerun()
    if col_p2.button("🏢 Ofi"):
        st.session_state['scale_px_per_meter'] = 25.0
        st.rerun()
    if col_p3.button("🏨 Hotel"):
        st.session_state['scale_px_per_meter'] = 15.0
        st.rerun()

    scale = st.number_input("Px por metro:", value=float(st.session_state['scale_px_per_meter']), step=1.0)
    if scale != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = scale
        st.rerun()
    
    st.caption("Usa la línea roja del mapa como guía de 1 metro.")
    st.divider()

    # --- 3. MODELOS Y SEMBRADO ---
    modo = st.radio("Herramienta:", ["📍 Sembrar Equipos", "📏 Calibrar Escala"], index=0)

    if modo == "📍 Sembrar Equipos":
        st.subheader("📦 Selección de Equipo")
        opciones = ["Advance Pro", "Plus Pro", "Extreme"]
        tipo = st.selectbox("Modelo", opciones)
        
        # LÓGICA DE CÁLCULO VOLUMÉTRICO
        if tipo == "Advance Pro":
            base_area = 150 # m2 a 3m de altura
            color = "#2E8B57" # Verde
        elif tipo == "Plus Pro":
            base_area = 200
            color = "#FF8C00" # Naranja
        else: # Extreme
            base_area = 800
            color = "#DC143C" # Rojo
            
        # Ajuste real
        area_real_cubierta = base_area * factor_altura
        radio_real = math.sqrt(area_real_cubierta / math.pi)
        radio_px = int(radio_real * st.session_state['scale_px_per_meter'])
        
        # Calculadora de Cantidad
        equipos_necesarios = math.ceil(area_total / area_real_cubierta)
        
        # Mostrar Métricas
        st.markdown(f"""
        <div class="metrics-box">
            <b>Cobertura Real (a {altura}m):</b> {area_real_cubierta:.1f} m²<br>
            <b>Radio visual:</b> {radio_real:.1f} m<br>
            <b>Sugerencia:</b> Necesitas {equipos_necesarios} equipos
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        if col1.button("↩️ Deshacer"):
            if st.session_state['puntos']:
                st.session_state['puntos'].pop()
                st.rerun()
        if col2.button("🗑️ Borrar Todo"):
            st.session_state['puntos'] = []
            st.rerun()

    else: # MODO CALIBRAR
        st.info("Clic A -> Clic B (en una puerta)")
        if len(st.session_state['calibracion_clicks']) == 2:
            p1 = st.session_state['calibracion_clicks'][0]
            p2 = st.session_state['calibracion_clicks'][1]
            dist_px = math.sqrt((p2['x'] - p1['x'])**2 + (p2['y'] - p1['y'])**2)
            st.write(f"📏 Pixeles: {dist_px:.1f}")
            metros = st.number_input("Metros reales:", value=0.90, step=0.10)
            if st.button("✅ Ajustar"):
                if metros > 0:
                    st.session_state['scale_px_per_meter'] = dist_px / metros
                    st.session_state['calibracion_clicks'] = []
                    st.rerun()
        if st.button("❌ Cancelar"):
            st.session_state['calibracion_clicks'] = []
            st.rerun()

    # --- API KEY ---
    st.divider()
    api_key = None
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        with st.expander("🔑 API Key (IA)", expanded=False):
            api_key = st.text_input("Key:", type="password")

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

    # --- ZONA IA ---
    if api_key and modo == "📍 Sembrar Equipos":
        col_btn, col_txt = st.columns([1, 4])
        with col_btn:
            if st.button("✨ Preguntar a Gemini"):
                try:
                    with st.spinner("Analizando..."):
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-flash-latest')
                        prompt = f"""
                        Actúa como experto en Marketing Olfativo.
                        Datos técnicos: Local de {area_total} m² con altura de {altura} m.
                        Analiza el plano visualmente. Dame 3 puntos estratégicos para difusores.
                        FORMATO: "📍 **[Zona]**: [Razón breve]"
                        """
                        response = model.generate_content([prompt, st.session_state['base_image']])
                        st.session_state['sugerencias_puntos'] = response.text
                        st.rerun()
                except Exception as e:
                    st.error(f"Error IA: {e}")
        
        with col_txt:
            if st.session_state['sugerencias_puntos']:
                with st.expander("💡 Sugerencias IA", expanded=True):
                    st.markdown(st.session_state['sugerencias_puntos'])

    # --- CANVAS ---
    display_img = st.session_state['base_image'].copy()
    draw = ImageDraw.Draw(display_img, "RGBA")
    
    # PUNTOS
    for p in st.session_state['puntos']:
        x, y = p['x'], p['y']
        r = p['radio']
        draw.ellipse((x-r, y-r, x+r, y+r), outline=p['color'], width=4)
        draw.ellipse((x-6, y-6, x+6, y+6), fill="white", outline="black")
        draw.ellipse((x-3, y-3, x+3, y+3), fill=p['color'])

    # CALIBRACIÓN
    clicks = st.session_state['calibracion_clicks']
    if len(clicks) > 0:
        p1 = clicks[0]
        draw.ellipse((p1['x']-5, p1['y']-5, p1['x']+5, p1['y']+5), fill="blue", outline="white")
        if len(clicks) == 2:
            p2 = clicks[1]
            draw.ellipse((p2['x']-5, p2['y']-5, p2['x']+5, p2['y']+5), fill="blue", outline="white")
            draw.line([(p1['x'], p1['y']), (p2['x'], p2['y'])], fill="blue", width=3)

    # TESTIGO 1 METRO
    px_m = st.session_state['scale_px_per_meter']
    draw.line([(30, display_img.height-30), (30+px_m, display_img.height-30)], fill="red", width=6)
    draw.text((30, display_img.height-55), "1m", fill="red") # Texto simple sin font externa

    # INTERACCIÓN
    if modo == "📍 Sembrar Equipos":
        st.write(f"📍 Equipos sembrados: **{len(st.session_state['puntos'])}**")
    else:
        st.info("📏 Calibración: Clic en dos puntos.")

    value = streamlit_image_coordinates(display_img, key="clicker")
    
    if value is not None:
        x, y = value["x"], value["y"]
        
        if modo == "📍 Sembrar Equipos":
            # Usamos el radio calculado dinámicamente arriba
            new_point = {"x": x, "y": y, "color": color, "radio": radio_px}
            if not st.session_state['puntos'] or st.session_state['puntos'][-1]['x'] != x:
                st.session_state['puntos'].append(new_point)
                st.rerun()
        elif modo == "📏 Calibrar Escala":
            if len(st.session_state['calibracion_clicks']) < 2:
                if not st.session_state['calibracion_clicks'] or st.session_state['calibracion_clicks'][-1]['x'] != x:
                    st.session_state['calibracion_clicks'].append({"x": x, "y": y})
                    st.rerun()

    # DESCARGA
    if st.session_state['puntos'] and modo == "📍 Sembrar Equipos":
        st.divider()
        if st.button("📸 Descargar"):
            buf = io.BytesIO()
            fig, ax = plt.subplots(figsize=(10, 10 * display_img.height / display_img.width))
            ax.imshow(st.session_state['base_image'])
            ax.axis('off')
            
            for p in st.session_state['puntos']:
                c = patches.Circle((p['x'], p['y']), p['radio'], color=p['color'], alpha=0.3)
                ax.add_patch(c)
                ax.add_patch(patches.Circle((p['x'], p['y']), 5, color="white"))
            
            # Testigo en descarga
            rect = patches.Rectangle((30, st.session_state['base_image'].height - 40), st.session_state['scale_px_per_meter'], 5, color='red')
            ax.add_patch(rect)
            ax.text(30, st.session_state['base_image'].height - 50, '1 Metro', color='red', fontsize=12, backgroundcolor='white')

            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
            st.download_button("Descargar PNG", buf.getvalue(), "sembrado_v38.png", "image/png")
