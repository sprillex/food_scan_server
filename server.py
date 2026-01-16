import os
import shutil
import uuid
import json
import asyncio
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from dotenv import load_dotenv
from PIL import Image

import database

# --- CONFIGURATION ---
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("foodscan.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize GenAI Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

# Directories
IMAGE_ROOT = "images"
PROMPT_DIR = "prompts"

# Run immediately on startup
database.init_db()

def validate_and_save_image(file_obj, path):
    """Validates that the file is an image and saves it."""
    try:
        # Verify it's an image
        with Image.open(file_obj) as img:
            img.verify()

        # Reset file pointer after verify
        file_obj.seek(0)

        # Save file
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)

    except Exception as e:
        logger.exception(f"Image validation failed: {e}")
        raise ValueError("Invalid image file.")

# --- API ENDPOINTS ---

@app.get("/product/{upc}")
async def check_product(upc: str):
    """
    Android Phase 5 Endpoint:
    Checks if we already know this UPC. 
    Returns the data if found, or a 404-like status if not.
    """
    print(f"🔎 [LOOKUP] Checking DB for UPC: {upc}")
    result = database.get_product_from_db(upc)
    
    if result:
        return {"status": "found", "data": result, "source": "Local DB"}
    else:
        return {"status": "not_found", "message": "Item unknown. Please scan label."}

@app.post("/analyze")
async def analyze_evidence(file: UploadFile = File(...)):
    logger.info(f"🔎 [RECEIVING] {file.filename}")

    # 1. Save Image Temporarily with Validation
    case_id = uuid.uuid4().hex[:8]
    case_folder = os.path.join(IMAGE_ROOT, f"scan_{case_id}")
    os.makedirs(case_folder, exist_ok=True)
    image_path = os.path.join(case_folder, "evidence.jpg")
    
    try:
        # Run blocking validation and file IO in thread
        await asyncio.to_thread(validate_and_save_image, file.file, image_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
    except Exception as e:
        logger.exception(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image.")

    # 2. GENERATE PROMPT
    prompt_path = os.path.join(PROMPT_DIR, "learning.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r') as f:
            prompt_text = f.read()
    else:
        # Fallback if file is missing
        prompt_text = "Analyze image. Extract UPC and Nutrition. Return valid JSON only."

    # 3. CALL GEMINI (New SDK)
    logger.info("   🤖 Asking Gemini to read label...")
    try:
        # With the new SDK, we can pass the image directly if it's small, or upload it.
        # For compatibility and large files, let's read it as bytes.
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Retry logic for 429 Rate Limits
        max_retries = 3
        base_delay = 5  # Start with 5 seconds
        response = None

        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model='gemini-2.0-flash',
                    contents=[
                        prompt_text,
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                    ]
                )
                break  # Success, exit loop
            except ClientError as e:
                if e.code == 429:
                    if attempt < max_retries - 1:
                        wait_time = base_delay * (2 ** attempt)
                        logger.warning(f"   ⏳ Rate limited (429). Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                raise e  # Re-raise if not 429 or max retries reached
            except Exception as e:
                raise e # Re-raise other exceptions

        result_text = response.text
        
        # 4. PARSE RESPONSE
        clean_json = result_text.replace("```json", "").replace("```", "").strip()
        
        try:
            analysis_data = json.loads(clean_json)
            
            # 5. LEARN (Save to DB)
            await asyncio.to_thread(database.save_product_to_db, analysis_data)
            
            # 6. RETURN RESULT
            return {"status": "success", "data": analysis_data, "source": "Gemini API"}
            
        except json.JSONDecodeError:
            logger.warning("   ⚠️ Gemini returned invalid JSON.")
            return {"status": "partial_success", "raw_text": result_text}

    except Exception as e:
        logger.exception(f"   🔴 Error: {e}")
        return {"status": "error", "message": str(e)}
