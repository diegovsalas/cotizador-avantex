import streamlit as st
from PIL import Image, ImageOps
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

st.title("🌱 Aromatex: Sembrado V6 (Fuerza Bruta)")

# --- GESTIÓN DE ESTADO (SESSION STATE) ---
if 'scale_px_per_meter' not in st.session_state:
    st.session_state['scale_px_per_meter'] = 35.0 
# NOTA: Hemos eliminado el caché de imagen para obligar a recargar
if 'bg_image' not in st.session_state:
    st.session_state['bg_image'] = None

# --- FUNCIONES AUXILIARES ---
def load_image(uploaded_file):
    # Eliminamos el "if" que comprobaba el nombre para FORZAR el procesamiento
    # Esto asegura que si subes el mismo archivo, se arregle el fondo.
    
    image = None
    
    if uploaded_file.type == "application/pdf":
        try:
            # 1. Abrir PDF
            doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
            page = doc.load_page(0)
            
            # 2. Renderizar a imagen
            # alpha=False: Pide a PyMuPDF que use fondo blanco (no transparente)
            mat = fitz.Matrix(2.0, 2.0) # Zoom 2x es suficiente y rápido
            pix = page.get_pixmap(matrix=mat, alpha=False) 
            
            # 3. Convertir a PIL
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # 4. Asegurar formato RGB (elimina cualquier transparencia residual)
            image = image.convert("RGB")
            
        except Exception as e:
            st.error(f"Error leyendo el PDF: {e}")
            return
            
    else:
        # Imágenes normales (JPG/PNG)
        try:
            image = Image.open(uploaded_file)
            # Si tiene transparencia (PNG), poner fondo blanco
            if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                alpha = image.convert('RGBA').split()[-1]
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=alpha)
                image = bg
            else:
                image = image.convert("RGB")
        except Exception as e:
            st.error(f"Error leyendo imagen: {e}")
            return
    
    # 5. Redimensionar para la web (evita que la imagen sea gigante y falle)
    if image:
        base_width = 1200
        w_percent = (base_width / float(image.size[0]))
        h_size = int((float(image.size[1]) * float(w_percent)))
        image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
        
        st.session_state['bg_image'] = image
        # Forzar recarga de la app para mostrar la nueva imagen
        # st.rerun()  <-- A veces causa bucles, mejor dejamos que fluya

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933190.png", width=50)
    st.header("1. Configuración")
    
    tipo_equipo = st.selectbox("Modelo de Difusor", 
        ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"])
    
    if "Home" in tipo_equipo:
        radio_real = 5.6
        color_hex = "#2E8B57" # Verde
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color_hex = "#FF8C00" # Naranja
    else:
        radio_real = 16.0
        color_hex = "#DC143C" # Rojo

    canvas_fill_color = color_hex + "44"  

    st.divider()
    modo = st.radio("Modo de trabajo:", ["📏 Calibrar Escala", "📍 Sembrar Equipos"], index=1)
    
    st.divider()
    st.subheader("⚙️ Ajuste Manual de Escala")
    
    escala_manual = st.number_input(
        "Píxeles por metro:", 
        value=float(st.session_state['scale_px_per_meter']),
        step=0.1,
        format="%.2f"
    )
    
    if escala_manual != st.session_state['scale_px_per_meter']:
        st.session_state['scale_px_per_meter'] = escala_manual
        st.rerun()

    radio_px_pantalla = int(radio_real * st.session_state['scale_px_per_meter'])
    st.caption(f"Radio cobertura: {radio_real}m ({radio_px_pantalla} px)")

    if st.button("🗑️ Limpiar Todo"):
        st.session_state['bg_image'] = None
        st.session_state['scale_px_per_meter'] = 35.0
        st.rerun()

# --- ÁREA PRINCIPAL ---
archivo = st.file_uploader("Sube el plano arquitectónico (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if archivo:
    # Llamamos a load_image siempre, ignorando caché
    load_image(archivo)
    
    if st.session_state['bg_image']:
        img = st.session_state['bg_image']
        
        # --- MODO CALIBRACIÓN ---
        if modo == "📏 Calibrar Escala":
            st.warning("MODO CALIBRACIÓN: Dibuja una línea de referencia.")
            
            canvas_calib = st_canvas(
                fill_color="rgba(0, 0, 0, 0)",
                stroke_width=3,
                stroke_color="#0000FF",
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="line",
                display_toolbar=True,
                key="canvas_calib"
            )
            
            if canvas_calib.json_data is not None:
                objects = canvas_calib.json_data["objects"]
                if len(objects) > 0:
                    last_obj = objects[-1]
                    width_obj = last_obj["width"] * last_obj["scaleX"]
                    height_obj = last_obj["height"] * last_obj["scaleY"]
                    dist_px = math.sqrt(width_obj**2 + height_obj**2)
                    
                    st.write(f"📏 Distancia trazada: **{dist_px:.1f} px**")
                    metros_reales = st.number_input("¿Cuántos metros son en la realidad?", value=1.0)
                    
                    if st.button("✅ Guardar Calibración"):
                        if metros_reales > 0:
                            nueva_escala = dist_px / metros_reales
                            st.session_state['scale_px_per_meter'] = nueva_escala
                            st.success(f"Escala guardada: {nueva_escala:.2f} px/m")
                            st.rerun()

        # --- MODO SEMBRADO ---
        elif modo == "📍 Sembrar Equipos":
            st.success(f"MODO SEMBRADO: Haz clic para colocar **{tipo_equipo}**")
            
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
                display_toolbar=True,
                key=f"canvas_sembrado_{tipo_equipo}_{st.session_state['scale_px_per_meter']}"
            )
            
            if canvas_sembrado.json_data is not None:
                objects = canvas_sembrado.json_data["objects"]
                
                if len(objects) > 0:
                    st.write("### 🖼️ Vista Previa y Descarga")
                    
                    fig, ax = plt.subplots(figsize=(12, 12 * img.height / img.width))
                    ax.imshow(img)
                    ax.axis('off')

                    conteo = 0
                    for obj in objects:
                        conteo += 1
                        x, y = obj["left"], obj["top"]
                        circ = patches.Circle((x, y), radio_px_pantalla, linewidth=2, edgecolor=color_hex, facecolor=color_hex, alpha=0.3)
                        ax.add_patch(circ)
                        center = patches.Circle((x, y), 5, color="white")
                        ax.add_patch(center)

                    st.markdown(f"**Equipos colocados:** {conteo}")

                    buf = io.BytesIO()
                    plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
                    buf.seek(0)
                    
                    st.download_button(
                        label="📥 Descargar Imagen Final",
                        data=buf,
                        file_name=f"Propuesta_Aromatex_{tipo_equipo}.png",
                        mime="image/png"
                    )

else:
    st.info("👆 Sube un plano para comenzar.")
