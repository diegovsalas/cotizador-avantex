import streamlit as st
from PIL import Image
import io
from streamlit_drawable_canvas import st_canvas
# CAMBIO: Usamos pdf2image en lugar de fitz
from pdf2image import convert_from_bytes 
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

st.title("🌱 Aromatex: Sembrado (Motor Poppler)")

# --- GESTIÓN DE ESTADO ---
if 'scale_px_per_meter' not in st.session_state:
    st.session_state['scale_px_per_meter'] = 35.0 
if 'bg_image' not in st.session_state:
    st.session_state['bg_image'] = None
# Cache ID para no recargar innecesariamente
if 'file_id' not in st.session_state:
    st.session_state['file_id'] = None

# --- FUNCIONES AUXILIARES ---
def load_image(uploaded_file):
    # Verificar si es un archivo nuevo
    current_file_id = uploaded_file.file_id if hasattr(uploaded_file, 'file_id') else uploaded_file.name
    
    if st.session_state['file_id'] != current_file_id:
        try:
            image = None
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()

            if uploaded_file.type == "application/pdf":
                # --- AQUÍ ESTÁ LA MAGIA DEL NUEVO MOTOR ---
                # Convertimos el PDF a imagen usando Poppler
                # Esto aplana todas las capas automáticamente (sin transparencias raras)
                images = convert_from_bytes(file_bytes, dpi=150, fmt="jpeg") 
                if images:
                    image = images[0] # Tomamos la primera página
            else:
                # Si es JPG/PNG
                image = Image.open(io.BytesIO(file_bytes))

            # Procesamiento final de imagen
            if image:
                # Asegurar RGB
                image = image.convert("RGB")
                
                # Redimensionar para evitar crashes de memoria en web
                base_width = 1200
                w_percent = (base_width / float(image.size[0]))
                h_size = int((float(image.size[1]) * float(w_percent)))
                image = image.resize((base_width, h_size), Image.Resampling.LANCZOS)
                
                st.session_state['bg_image'] = image
                st.session_state['file_id'] = current_file_id
            
        except Exception as e:
            st.error(f"Error al procesar el archivo. Si el error menciona 'poppler', verifica que creaste el archivo packages.txt. Detalle: {e}")

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
    st.subheader("⚙️ Ajuste Manual")
    
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
    st.caption(f"Radio: {radio_real}m ({radio_px_pantalla} px)")

    if st.button("🗑️ Reiniciar"):
        st.session_state['bg_image'] = None
        st.session_state['file_id'] = None
        st.rerun()

# --- ÁREA PRINCIPAL ---
archivo = st.file_uploader("Sube el plano (PDF Recomendado)", type=["pdf", "jpg", "png"])

if archivo:
    load_image(archivo)
    
    if st.session_state['bg_image']:
        img = st.session_state['bg_image']
        
        # --- MODO CALIBRACIÓN ---
        if modo == "📏 Calibrar Escala":
            st.info("Dibuja una línea sobre una medida conocida (ej. puerta de 0.90m)")
            
            canvas_calib = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=3,
                stroke_color="#0000FF",
                background_image=img,
                update_streamlit=True,
                height=img.height,
                width=img.width,
                drawing_mode="line",
                display_toolbar=True,
                key="calib_canvas"
            )
            
            if canvas_calib.json_data and canvas_calib.json_data["objects"]:
                obj = canvas_calib.json_data["objects"][-1]
                # Cálculo de distancia simple
                dist_px = math.sqrt((obj["width"] * obj["scaleX"])**2 + (obj["height"] * obj["scaleY"])**2)
                
                st.write(f"Longitud: **{dist_px:.1f} px**")
                metros = st.number_input("Metros reales:", value=1.0)
                
                if st.button("✅ Aplicar Escala"):
                    if metros > 0:
                        st.session_state['scale_px_per_meter'] = dist_px / metros
                        st.success("Escala calibrada.")
                        st.rerun()

        # --- MODO SEMBRADO ---
        elif modo == "📍 Sembrar Equipos":
            st.success(f"Colocando: **{tipo_equipo}**")
            
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
                key=f"sembrado_{tipo_equipo}_{st.session_state['scale_px_per_meter']}"
            )
            
            if canvas_sembrado.json_data and canvas_sembrado.json_data["objects"]:
                st.write("### ⬇️ Descargar Propuesta")
                conteo = len(canvas_sembrado.json_data["objects"])
                
                # Generar imagen final con Matplotlib
                fig, ax = plt.subplots(figsize=(10, 10 * img.height / img.width))
                ax.imshow(img)
                ax.axis('off')

                for obj in canvas_sembrado.json_data["objects"]:
                    x, y = obj["left"], obj["top"]
                    ax.add_patch(patches.Circle((x, y), radio_px_pantalla, color=color_hex, alpha=0.3))
                    ax.add_patch(patches.Circle((x, y), 5, color="white"))

                st.markdown(f"**Total Equipos:** {conteo}")

                buf = io.BytesIO()
                plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, dpi=150)
                buf.seek(0)
                
                st.download_button("📥 Descargar Imagen", data=buf, file_name="Propuesta.png", mime="image/png")

else:
    st.info("👆 Sube tu plano para comenzar.")
