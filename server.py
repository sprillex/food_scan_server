import os
import shutil
import uuid
import json
import sqlite3
import piexif
from fastapi import FastAPI, File, UploadFile, Form
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

# Directories
IMAGE_ROOT = "images"
PROMPT_DIR = "prompts"
DB_FILE = "food_knowledge.db"

# --- DATABASE SETUP ---
def init_db():
    """Creates the table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        upc TEXT PRIMARY KEY,
        item_name TEXT,
        calories INTEGER,
        fat_g REAL,
        carbs_g REAL,
        protein_g REAL,
        brand_name TEXT
    )''')
    conn.commit()
    conn.close()

# Run immediately on startup
init_db()

# --- DB FUNCTIONS ---
def get_product_from_db(upc):
    if not upc: return None
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE upc = ?", (upc,))
    row = c.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def save_product_to_db(data):
    """Parses Gemini JSON response and saves to DB if UPC exists."""
    try:
        # Expecting data to look like: {'variables': {'Granola Bar': {'upc': '...', ...}}}
        # We need to dig into the structure.
        # Note: This parsing depends heavily on your Prompt Output structure.
        
        # Simple flattener for the 'variables' block structure you designed
        vars_block = data.get("variables", {})
        first_key = next(iter(vars_block)) # e.g., "Chewy Granola Bar"
        item_data = vars_block[first_key]
        
        upc = item_data.get("upc")
        if not upc or upc == "null":
            print("   ⚠️ No UPC found in analysis. Not saving to DB.")
            return

        print(f"   💾 [LEARNING] Saving {first_key} (UPC: {upc}) to Database.")
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO products 
            (upc, item_name, calories, fat_g, carbs_g, protein_g, brand_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', 
            (
                str(upc),
                item_data.get("name", first_key),
                item_data.get("calories", 0),
                item_data.get("fat", 0),
                item_data.get("carbohydrates", 0),
                item_data.get("protein", 0),
                item_data.get("brand_name", "Unknown")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Database Save Failed: {e}")

# --- API ENDPOINT ---
@app.post("/analyze")
async def analyze_evidence(file: UploadFile = File(...)):
    print(f"\n🔎 [RECEIVING] {file.filename}")

    # 1. Save Image Temporarily
    case_id = uuid.uuid4().hex[:8]
    case_folder = os.path.join(IMAGE_ROOT, f"scan_{case_id}")
    os.makedirs(case_folder, exist_ok=True)
    image_path = os.path.join(case_folder, f"evidence.jpg")
    
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Extract Metadata (Look for UPC from Android)
    # We assume Android might write UPC to UserComment or we just rely on Gemini
    # For now, let's assume we rely on Gemini to find the UPC in the photo first.
    
    # 3. GENERATE PROMPT (Using a specific "Learning" template)
    # We will use a hardcoded fallback if file is missing, or load 'learning.txt'
    prompt_path = os.path.join(PROMPT_DIR, "learning.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r') as f:
            prompt_text = f.read()
    else:
        # Fallback Prompt logic
        prompt_text = "Analyze image. Extract UPC, Calories, Fat, Carbs, Protein. Format as JSON variables."

    # 4. CALL GEMINI
    print("   🤖 Asking Gemini to read label...")
    try:
        uploaded_file = genai.upload_file(image_path)
        response = model.generate_content([prompt_text, uploaded_file])
        result_text = response.text
        
        # 5. PARSE RESPONSE
        # Clean up markdown code blocks if present (```json ... ```)
        clean_json = result_text.replace("```json", "").replace("```", "").strip()
        
        try:
            analysis_data = json.loads(clean_json)
            
            # 6. LEARN (Save to DB)
            save_product_to_db(analysis_data)
            
            # 7. RETURN RESULT
            return {"status": "success", "data": analysis_data, "source": "Gemini API"}
            
        except json.JSONDecodeError:
            print("   ⚠️ Gemini returned invalid JSON.")
            return {"status": "partial_success", "raw_text": result_text}

    except Exception as e:
        print(f"   🔴 Error: {e}")
        return {"status": "error", "message": str(e)}

# Run: uvicorn server:app --host 0.0.0.0 --port 8000
