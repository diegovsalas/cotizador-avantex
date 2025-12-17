import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
import fitz  # PyMuPDF para leer PDFs
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sembrado Automático Avantex", layout="wide")

st.title("🌱 Generador de Propuestas de Aromatización")
st.markdown("Sube el plano, selecciona el equipo y marca los puntos de instalación.")

# --- BARRA LATERAL: CONFIGURACIÓN ---
with st.sidebar:
    st.header("1. Configuración del Equipo")
    modelo = st.selectbox("Selecciona el Modelo", 
                          ["Difusor S (100 m2)", "Difusor M (300 m2)", "Difusor L (800 m2)"])
    
    # Definir radio de cobertura en metros (aprox)
    if "100" in modelo:
        radio_metros = 5.6  # r = raiz(100/pi)
        color_circulo = "#2E8B57" # Verde
    elif "300" in modelo:
        radio_metros = 9.7
        color_circulo = "#FF8C00" # Naranja
    else:
        radio_metros = 16.0
        color_circulo = "#FF0000" # Rojo

    st.divider()
    st.header("2. Escala del Plano")
    # Esto es crucial: ¿Cuántos pixeles son 1 metro en tu imagen?
    escala_px = st.slider("Píxeles por metro (Calibración)", 10, 100, 35)
    
    radio_px = radio_metros * escala_px
    st.info(f"Radio de cobertura calculado: {radio_px:.1f} píxeles")

# --- ÁREA PRINCIPAL: CARGA DE ARCHIVO ---
archivo = st.file_uploader("Sube el plano (PDF, JPG, PNG)", type=["pdf", "jpg", "png"])

if archivo:
    # Procesar archivo (PDF a Imagen o Imagen directa)
    if archivo.type == "application/pdf":
        doc = fitz.open(stream=archivo.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img_data = pix.tobytes("png")
        bg_image = Image.open(io.BytesIO(img_data))
    else:
        bg_image = Image.open(archivo)

    # Redimensionar para que quepa en pantalla si es muy grande
    ancho_base = 800
    w_percent = (ancho_base / float(bg_image.size[0]))
    h_size = int((float(bg_image.size[1]) * float(w_percent)))
    bg_image = bg_image.resize((ancho_base, h_size), Image.Resampling.LANCZOS)

    st.write("### 📍 Da clic en el plano donde quieras colocar los equipos")
    
    # --- CANVAS INTERACTIVO ---
    # Esto permite dar clic sobre la imagen y recuperar las coordenadas
    canvas_result = st_canvas(
        fill_color=color_circulo + "44",  # Color con transparencia
        stroke_width=2,
        stroke_color=color_circulo,
        background_image=bg_image,
        update_streamlit=True,
        height=h_size,
        width=ancho_base,
        drawing_mode="point", # Modo solo puntos
        point_display_radius=0, # Ocultar punto guía del mouse
        key="canvas",
    )

    # --- LÓGICA DE DIBUJADO AUTOMÁTICO ---
    # Si el usuario dio clic, obtenemos las coordenadas y dibujamos los círculos de cobertura
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        if len(objects) > 0:
            st.success(f"Se han colocado {len(objects)} equipos.")
            
            # Aquí generamos la imagen final para descargar
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.imshow(bg_image)
            ax.axis('off')

            for obj in objects:
                # Coordenadas del clic
                x, y = obj["left"], obj["top"]
                # Dibujar círculo de cobertura real
                circ = patches.Circle((x, y), radio_px, linewidth=2, edgecolor=color_circulo, facecolor=color_circulo+"44")
                ax.add_patch(circ)
                # Etiqueta
                ax.text(x, y, "Difusor", color="white", fontsize=8, ha="center", weight="bold", 
                        bbox=dict(facecolor=color_circulo, edgecolor='none', alpha=0.8))

            # Guardar en memoria para descarga
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0)
            buf.seek(0)
            
            st.download_button(
                label="📥 Descargar Propuesta Final",
                data=buf,
                file_name="Propuesta_Sembrado.png",
                mime="image/png"
            )

else:
    st.info("Esperando archivo...")