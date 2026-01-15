import os
import shutil
import uuid
import json
import sqlite3
from fastapi import FastAPI, File, UploadFile
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ ERROR: GEMINI_API_KEY not found in .env file.")

genai.configure(api_key=API_KEY)

# Using 'gemini-flash-latest' for the best balance of free-tier access and speed
model = genai.GenerativeModel('gemini-flash-latest')

app = FastAPI()

# Directories
IMAGE_ROOT = "images"
PROMPT_DIR = "prompts"
DB_FILE = "food_knowledge.db"

# Ensure directories exist
os.makedirs(IMAGE_ROOT, exist_ok=True)
os.makedirs(PROMPT_DIR, exist_ok=True)

# --- DATABASE SETUP ---
def init_db():
    """Creates the table with all nutritional columns if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        upc TEXT PRIMARY KEY,
        item_name TEXT,
        calories INTEGER,
        fat_g REAL,
        carbs_g REAL,
        protein_g REAL,
        fiber_g REAL,
        sodium_mg INTEGER,
        brand_name TEXT,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# Run immediately on startup
init_db()

# --- DB HELPER FUNCTIONS ---
def get_product_from_db(upc):
    """Retrieves a product by UPC from the local SQLite database."""
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
    """Parses Gemini JSON response and saves to DB if a valid UPC is found."""
    try:
        # We expect the data structure: {'variables': {'Item Name': {'upc': '...', ...}}}
        vars_block = data.get("variables", {})
        if not vars_block: 
            return
        
        # Get the first item in the variables list
        first_key = next(iter(vars_block))
        item_data = vars_block[first_key]
        
        upc = item_data.get("upc")
        
        # Validation: Don't save if there is no UPC
        if not upc or upc == "null":
            print("   ⚠️ No UPC found in analysis. Not saving to DB.")
            return

        print(f"   💾 [LEARNING] Saving '{first_key}' (UPC: {upc}) to Database.")
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Insert or Overwrite the data
        c.execute('''INSERT OR REPLACE INTO products 
            (upc, item_name, calories, fat_g, carbs_g, protein_g, fiber_g, sodium_mg, brand_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
            (
                str(upc),
                item_data.get("name", first_key),
                item_data.get("calories", 0),
                item_data.get("fat", 0),
                item_data.get("carbohydrates", 0),
                item_data.get("protein", 0),
                item_data.get("fiber", 0),
                item_data.get("sodium", 0),
                item_data.get("brand_name", "Unknown")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Database Save Failed: {e}")

# --- API ENDPOINTS ---

@app.get("/product/{upc}")
async def check_product(upc: str):
    """
    Android Phase 5 Endpoint:
    Checks if we already know this UPC. 
    Returns the data if found, or a 404-like status if not.
    """
    print(f"🔎 [LOOKUP] Checking DB for UPC: {upc}")
    result = get_product_from_db(upc)
    
    if result:
        return {"status": "found", "data": result, "source": "Local DB"}
    else:
        return {"status": "not_found", "message": "Item unknown. Please scan label."}

@app.post("/analyze")
async def analyze_evidence(file: UploadFile = File(...)):
    """
    Main Endpoint:
    1. Receives image.
    2. Sends to Gemini (AI).
    3. Returns analysis + Saves to DB (Learning).
    """
    print(f"\n🔎 [RECEIVING] {file.filename}")

    # 1. Save Image Temporarily
    case_id = uuid.uuid4().hex[:8]
    case_folder = os.path.join(IMAGE_ROOT, f"scan_{case_id}")
    os.makedirs(case_folder, exist_ok=True)
    image_path = os.path.join(case_folder, "evidence.jpg")
    
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Load Prompt
    prompt_path = os.path.join(PROMPT_DIR, "learning.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r') as f:
            prompt_text = f.read()
    else:
        # Fallback if file is missing
        prompt_text = "Analyze image. Extract UPC and Nutrition. Return valid JSON only."

    # 3. Call Gemini
    print("   🤖 Asking Gemini to read label...")
    try:
        uploaded_file = genai.upload_file(image_path)
        
        # Generate content
        response = model.generate_content([prompt_text, uploaded_file])
        result_text = response.text
        
        # 4. Clean & Parse JSON
        clean_json = result_text.replace("```json", "").replace("```", "").strip()
        
        try:
            analysis_data = json.loads(clean_json)
            
            # 5. LEARN (Save to DB)
            save_product_to_db(analysis_data)
            
            # 6. Return Result
            return {"status": "success", "data": analysis_data, "source": "Gemini API"}
            
        except json.JSONDecodeError:
            print("   ⚠️ Gemini returned invalid JSON.")
            print(f"   Raw output: {result_text[:100]}...") # Print first 100 chars for debug
            return {"status": "partial_success", "raw_text": result_text}

    except Exception as e:
        print(f"   🔴 Error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
