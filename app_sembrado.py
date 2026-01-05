import streamlit as st
from PIL import Image
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

# --- SESSION STATE ---
if "scale_px_per_meter" not in st.session_state:
    st.session_state.scale_px_per_meter = 35.0

if "bg_image" not in st.session_state:
    st.session_state.bg_image = None

# --- FUNCIÓN DE CARGA ---
def load_image(uploaded_file):
    image = None

    if uploaded_file.type == "application/pdf":
        try:
            pdf_bytes = uploaded_file.getvalue()  # ✅ FIX CLAVE
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc.load_page(0)

            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data)).convert("RGB")

        except Exception as e:
            st.error(f"Error leyendo el PDF: {e}")
            return

    else:
        try:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[-1])
                image = bg
            else:
                image = image.convert("RGB")
        except Exception as e:
            st.error(f"Error leyendo imagen: {e}")
            return

    # Redimensionar
    if image:
        base_width = 1200
        scale = base_width / image.width
        image = image.resize(
            (base_width, int(image.height * scale)),
            Image.Resampling.LANCZOS
        )
        st.session_state.bg_image = image

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Configuración")

    tipo_equipo = st.selectbox(
        "Modelo de Difusor",
        ["Home Pro (100 m²)", "Advance Pro (300 m²)", "Extreme (800 m²)"]
    )

    if "Home" in tipo_equipo:
        radio_real = 5.6
        color_hex = "#2E8B57"
    elif "Advance" in tipo_equipo:
        radio_real = 9.7
        color_hex = "#FF8C00"
    else:
        radio_real = 16.0
        color_hex = "#DC143C"

    canvas_fill_color = color_hex + "44"

    modo = st.radio(
        "Modo de trabajo:",
        ["📏 Calibrar Escala", "📍 Sembrar Equipos"],
        index=1
    )

    st.subheader("⚙️ Ajuste Manual de Escala")

    escala_manual = st.number_input(
        "Píxeles por metro",
        value=float(st.session_state.scale_px_per_meter),
        step=0.1
    )

    if escala_manual != st.session_state.scale_px_per_meter:
        st.session_state.scale_px_per_meter = escala_manual
        st.rerun()

    radio_px = int(radio_real * st.session_state.scale_px_per_meter)
    st.caption(f"Radio cobertura: {radio_real} m ({radio_px} px)")

    if st.button("🗑️ Limpiar Todo"):
        st.session_state.bg_image = None
        st.session_state.scale_px_per_meter = 35.0
        st.rerun()

# --- MAIN ---
archivo = st.file_uploader(
    "Sube el plano arquitectónico (PDF, JPG, PNG)",
    type=["pdf", "jpg", "png"]
)

if archivo:
    load_image(archivo)

    if st.session_state.bg_image:
        img = st.session_state.bg_image

        # --- CALIBRACIÓN ---
        if modo == "📏 Calibrar Escala":
            st.warning("Dibuja una línea de referencia")

            canvas = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=3,
                stroke_color="#0000FF",
                background_image=img,
                height=img.height,
                width=img.width,
                drawing_mode="line",
                key="canvas_calib"
            )

            if canvas.json_data and canvas.json_data["objects"]:
                obj = canvas.json_data["objects"][-1]
                dist_px = math.hypot(
                    obj["width"] * obj["scaleX"],
                    obj["height"] * obj["scaleY"]
                )

                st.write(f"Distancia: {dist_px:.1f} px")

                metros = st.number_input("Metros reales", value=1.0)

                if st.button("Guardar calibración"):
                    if metros > 0:
                        st.session_state.scale_px_per_meter = dist_px / metros
                        st.success("Escala guardada")
                        st.rerun()

        # --- SEMBRADO ---
        else:
            st.success(f"Haz clic para colocar {tipo_equipo}")

            canvas = st_canvas(
                fill_color=canvas_fill_color,
                stroke_width=2,
                stroke_color=color_hex,
                background_image=img,
                height=img.height,
                width=img.width,
                drawing_mode="point",
                point_display_radius=radio_px,
                key=f"canvas_{tipo_equipo}_{st.session_state.scale_px_per_meter}"
            )

            if canvas.json_data and canvas.json_data["objects"]:
                fig, ax = plt.subplots(figsize=(12, 12 * img.height / img.width))
                ax.imshow(img)
                ax.axis("off")

                for obj in canvas.json_data["objects"]:
                    x, y = obj["left"], obj["top"]
                    ax.add_patch(
                        patches.Circle(
                            (x, y),
                            radio_px,
                            edgecolor=color_hex,
                            facecolor=color_hex,
                            alpha=0.3
                        )
                    )

                buf = io.BytesIO()
                plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                buf.seek(0)

                st.download_button(
                    "📥 Descargar Imagen Final",
                    buf,
                    file_name="Propuesta_Aromatex.png",
                    mime="image/png"
                )

else:
    st.info("👆 Sube un plano para comenzar")
