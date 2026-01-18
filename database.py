import sqlite3
import logging

# Configure logging
logger = logging.getLogger(__name__)

DB_FILE = "food_knowledge.db"

def init_db():
    """Creates the table if it doesn't exist and ensures schema is up to date."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Create table with all columns if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        upc TEXT PRIMARY KEY,
        item_name TEXT,
        brand_name TEXT,
        srv_per_cont REAL,
        calories INTEGER,
        fat_g REAL,
        cholesterol_mg REAL,
        sodium_mg REAL,
        carbs_g REAL,
        fiber_g REAL,
        total_sugars_g REAL,
        added_sugars_g REAL,
        protein_g REAL,
        vit_d_mcg REAL,
        calcium_mg REAL,
        iron_mg REAL,
        potassium_mg REAL,
        serving_size TEXT,
        score_color TEXT,
        health_insight TEXT,
        pairing_tip TEXT
    )''')

    conn.commit()
    conn.close()

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
        # Expecting data to look like: {'variables': {'Granola Bar': {'metadata': {...}, 'macros': {...}, ...}}}
        vars_block = data.get("variables", {})
        if not vars_block:
             logger.warning("No 'variables' block found in data.")
             return

        first_key = next(iter(vars_block)) # e.g., "Chewy Granola Bar"
        item_data = vars_block[first_key]

        # Extract sections
        metadata = item_data.get("metadata", {})
        macros = item_data.get("macros", {})
        micros = item_data.get("micros", {})
        serving_info = item_data.get("serving_info", {})
        analysis = item_data.get("analysis", {})

        upc = metadata.get("upc")
        if not upc or upc == "null":
             # Fallback to top level if not in metadata, or legacy structure
            upc = item_data.get("upc")

        if not upc or upc == "null":
            logger.warning("⚠️ No UPC found in analysis. Not saving to DB.")
            return

        logger.info(f"💾 [LEARNING] Saving {first_key} (UPC: {upc}) to Database.")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO products
            (upc, item_name, brand_name, srv_per_cont,
             calories, fat_g, cholesterol_mg, sodium_mg, carbs_g, fiber_g, total_sugars_g, added_sugars_g, protein_g,
             vit_d_mcg, calcium_mg, iron_mg, potassium_mg,
             serving_size, score_color, health_insight, pairing_tip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                str(upc),
                metadata.get("name", first_key),
                metadata.get("brand"),
                metadata.get("srv_per_cont"),

                macros.get("calories"),
                macros.get("fat_g"),
                macros.get("cholesterol_mg"),
                macros.get("sodium_mg"),
                macros.get("carbs_g"),
                macros.get("fiber_g"),
                macros.get("total_sugars_g"),
                macros.get("added_sugars_g"),
                macros.get("protein_g"),

                micros.get("vit_d_mcg"),
                micros.get("calcium_mg"),
                micros.get("iron_mg"),
                micros.get("potassium_mg"),

                serving_info.get("size"),
                analysis.get("score_color"),
                analysis.get("health_insight"),
                analysis.get("pairing_tip")
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.exception(f"⚠️ Database Save Failed: {e}")
