import sqlite3
import logging

# Configure logging
logger = logging.getLogger(__name__)

DB_FILE = "food_knowledge.db"

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
        vars_block = data.get("variables", {})
        if not vars_block:
             logger.warning("No 'variables' block found in data.")
             return

        first_key = next(iter(vars_block)) # e.g., "Chewy Granola Bar"
        item_data = vars_block[first_key]

        upc = item_data.get("upc")
        if not upc or upc == "null":
            logger.warning("⚠️ No UPC found in analysis. Not saving to DB.")
            return

        logger.info(f"💾 [LEARNING] Saving {first_key} (UPC: {upc}) to Database.")

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
        logger.exception(f"⚠️ Database Save Failed: {e}")
