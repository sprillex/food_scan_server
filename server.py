import os
import shutil
import uuid
import json
import asyncio
import logging
from fastapi import FastAPI, File, UploadFile
import google.generativeai as genai
from dotenv import load_dotenv

import database

# --- CONFIGURATION ---
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

app = FastAPI()

# Directories
IMAGE_ROOT = "images"
PROMPT_DIR = "prompts"

# Run immediately on startup
database.init_db()

def save_file_sync(file_obj, path):
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file_obj, buffer)

# --- API ENDPOINT ---
@app.post("/analyze")
async def analyze_evidence(file: UploadFile = File(...)):
    logger.info(f"🔎 [RECEIVING] {file.filename}")

    # 1. Save Image Temporarily
    case_id = uuid.uuid4().hex[:8]
    case_folder = os.path.join(IMAGE_ROOT, f"scan_{case_id}")
    os.makedirs(case_folder, exist_ok=True)
    image_path = os.path.join(case_folder, f"evidence.jpg")
    
    # Run blocking file IO in thread
    # We access file.file which is the underlying blocking file object
    await asyncio.to_thread(save_file_sync, file.file, image_path)

    # 3. GENERATE PROMPT
    prompt_path = os.path.join(PROMPT_DIR, "learning.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r') as f:
            prompt_text = f.read()
    else:
        # Fallback Prompt logic
        prompt_text = "Analyze image. Extract UPC, Calories, Fat, Carbs, Protein. Format as JSON variables."

    # 4. CALL GEMINI
    logger.info("   🤖 Asking Gemini to read label...")
    try:
        # Uploading file to Gemini
        uploaded_file = await asyncio.to_thread(genai.upload_file, image_path)

        # Generate content
        # Using generate_content_async if available, else thread
        if hasattr(model, 'generate_content_async'):
             response = await model.generate_content_async([prompt_text, uploaded_file])
        else:
             response = await asyncio.to_thread(model.generate_content, [prompt_text, uploaded_file])

        result_text = response.text
        
        # 5. PARSE RESPONSE
        clean_json = result_text.replace("```json", "").replace("```", "").strip()
        
        try:
            analysis_data = json.loads(clean_json)
            
            # 6. LEARN (Save to DB)
            await asyncio.to_thread(database.save_product_to_db, analysis_data)
            
            # 7. RETURN RESULT
            return {"status": "success", "data": analysis_data, "source": "Gemini API"}
            
        except json.JSONDecodeError:
            logger.warning("   ⚠️ Gemini returned invalid JSON.")
            return {"status": "partial_success", "raw_text": result_text}

    except Exception as e:
        logger.error(f"   🔴 Error: {e}")
        return {"status": "error", "message": str(e)}
