import streamlit as st
import replicate
from PIL import Image, ImageFilter, ImageDraw
import io
import tempfile
import zipfile
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="BulkLister AI", page_icon="📦", layout="wide")

# --- CSS STYLING ---
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #111827; }
    .sub-header { font-size: 1.1rem; color: #6B7280; margin-bottom: 2rem; }
    .stButton>button { width: 100%; background-color: #2563EB; color: white; height: 3rem; font-size: 1.1rem; border-radius: 8px; }
    .warning-box { border: 1px solid #FCD34D; background-color: #FFFBEB; padding: 1rem; border-radius: 8px; color: #92400E; margin-bottom: 1rem; }
    .success-box { border: 1px solid #34D399; background-color: #ECFDF5; padding: 1rem; border-radius: 8px; color: #065F46; }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def get_color_hex(color_name):
    """Returns Hex codes for reseller backgrounds"""
    colors = {
        "Pure White (Amazon/eBay)": "#FFFFFF",
        "Light Gray (Professional)": "#F3F4F6",
        "Soft Pink (Poshmark)": "#FCE7F3",
        "Cream / Off-White": "#FDFBF7",
        "Navy Blue (Luxury)": "#1E3A8A",
        "Charcoal (Contrast)": "#374151"
    }
    return colors.get(color_name, "#FFFFFF")

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_shadow(img_size):
    """Generates a realistic oval shadow"""
    shadow = Image.new('RGBA', img_size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    w, h = img_size
    # Shadow sits at bottom, width 60% of canvas
    x0 = int(w * 0.2)
    y0 = int(h * 0.85)
    x1 = int(w * 0.8)
    y1 = int(h * 0.95)
    shadow_draw.ellipse([x0, y0, x1, y1], fill=(30, 30, 30, 50))
    return shadow.filter(ImageFilter.GaussianBlur(radius=30))

def process_single_image(file_data, filename, api_key, bg_hex, target_size):
    try:
        # 1. Throttle slightly to prevent API choking
        time.sleep(0.1) 
        os.environ["REPLICATE_API_TOKEN"] = api_key
        
        # 2. AI Removal (InSPyReNet Model)
        output_url = replicate.run(
            "851-labs/background-remover:a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc",
            input={"image": file_data, "format": "png"}
        )
        
        # 3. Download Cutout
        response = requests.get(output_url, timeout=60)
        cutout = Image.open(io.BytesIO(response.content)).convert("RGBA")
        
        # 4. Prepare Canvas (Color & Size)
        bg_rgb = hex_to_rgb(bg_hex)
        canvas = Image.new("RGB", target_size, bg_rgb)
        
        # 5. Smart Resize (Fit to 85% of canvas)
        target_w, target_h = target_size
        max_w = int(target_w * 0.85)
        max_h = int(target_h * 0.85)
        cutout.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        
        # 6. Add Shadow
        shadow = create_shadow(target_size)
        canvas.paste(shadow, (0,0), mask=shadow)
        
        # 7. Center & Paste Object
        paste_x = (target_w - cutout.width) // 2
        paste_y = (target_h - cutout.height) // 2
        canvas.paste(cutout, (paste_x, paste_y), mask=cutout)
        
        # 8. Save
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        canvas.save(temp.name, format="PNG", quality=95)
        return {"success": True, "filename": filename, "path": temp.name}
        
    except Exception as e:
        return {"success": False, "filename": filename, "error": str(e)}

# --- MAIN APPLICATION ---

st.markdown('<p class="main-header">📦 BulkLister AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">The Production Line for Resellers. 5x Speed. Compliance Ready.</p>', unsafe_allow_html=True)

# SIDEBAR
with st.sidebar:
    st.header("🎨 Output Settings")
    
    # Marketplace Presets
    size_choice = st.selectbox(
        "Target Marketplace",
        ["Square (Amazon/eBay) - 1600x1600", 
         "Portrait (Poshmark) - 1200x1600", 
         "Landscape (Shopify) - 1600x1200"]
    )
    
    if "Square" in size_choice: target_size = (1600, 1600)
    elif "Portrait" in size_choice: target_size = (1200, 1600)
    else: target_size = (1600, 1200)
    
    # Color Picker
    color_choice = st.selectbox(
        "Background Color",
        ["Pure White (Amazon/eBay)", "Light Gray (Professional)", "Soft Pink (Poshmark)", "Cream / Off-White", "Navy Blue (Luxury)", "Charcoal (Contrast)"]
    )
    bg_hex = get_color_hex(color_choice)
    
    st.divider()
    st.header("🔑 License Access")
    user_key = st.text_input("Enter License Key", type="password")
    
    # UNLIMITED KEY LOGIC
    valid_keys = ["UNLIMITED-2025"] 
    is_unlocked = user_key in valid_keys
    
    if is_unlocked:
        st.success("✅ ACTIVE: Unlimited Plan")
    else:
        st.warning("🔒 Enter Key to Unlock")

# UPLOAD SECTION
uploaded_files = st.file_uploader(
    "Select Images (Batch Safety Limit: 50)", 
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'webp']
)

if uploaded_files:
    total_selected = len(uploaded_files)
    batch_to_process = uploaded_files[:50] # Hard Limit
    
    if total_selected > 50:
        st.markdown(f"""
        <div class="warning-box">
            ⚠️ <b>BATCH LIMIT REACHED:</b> You selected {total_selected} images. 
            To prevent browser crashes, we will process the <b>first 50</b>. 
            Please upload the rest in the next batch.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info(f"✅ Ready to process {total_selected} images.")

    if st.button("🚀 PROCESS BATCH"):
        if not is_unlocked:
            st.error("🔒 Please enter a valid License Key.")
        else:
            try:
                my_secret_key = st.secrets["REPLICATE_API_TOKEN"]
            except:
                st.error("❌ Critical Error: Add REPLICATE_API_TOKEN to Streamlit Secrets.")
                st.stop()

            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            # PARALLEL PROCESSING (5 Workers)
            with ThreadPoolExecutor(max_workers=5) as executor:
                status_text.text("🔥 Starting 5 Parallel Workers...")
                
                futures = {executor.submit(process_single_image, f.getvalue(), f.name, my_secret_key, bg_hex, target_size): f.name for f in batch_to_process}
                
                completed = 0
                for future in as_completed(futures):
                    res = future.result()
                    results.append(res)
                    completed += 1
                    progress_bar.progress(completed / len(batch_to_process))
                    status_text.text(f"Processing... {completed}/{len(batch_to_process)}")
            
            # ZIP & DOWNLOAD
            zip_buffer = io.BytesIO()
            success_count = 0
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for r in results:
                    if r["success"]:
                        clean_name = os.path.splitext(r['filename'])[0] + "_clean.png"
                        zf.write(r["path"], clean_name)
                        os.unlink(r["path"])
                        success_count += 1
            
            st.markdown(f"""
            <div class="success-box">
                ✅ <b>JOB COMPLETE!</b> {success_count} images processed.
            </div>
            """, unsafe_allow_html=True)
            
            st.download_button(
                label="⬇️ Download ZIP Batch",
                data=zip_buffer.getvalue(),
                file_name="bulklister_batch.zip",
                mime="application/zip",
                type="primary"
            )
