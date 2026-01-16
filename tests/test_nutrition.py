import unittest
import sqlite3
import os
import database

class TestNutritionLogging(unittest.TestCase):

    def setUp(self):
        # Use a separate test database or ensure clean state
        self.test_db = "test_food_knowledge.db"
        # Temporarily swap the database file
        self.original_db_file = database.DB_FILE
        database.DB_FILE = self.test_db
        database.init_db()

    def tearDown(self):
        # Restore original DB file and clean up test DB
        database.DB_FILE = self.original_db_file
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_schema_and_logging(self):
        # Inspect schema
        conn = sqlite3.connect(self.test_db)
        c = conn.cursor()
        c.execute("PRAGMA table_info(products)")
        columns = [info[1] for info in c.fetchall()]
        conn.close()

        required_columns = ["fat_g", "carbs_g", "protein_g", "fiber_g", "sodium_mg"]
        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} is missing from schema")

        # Test Saving
        dummy_upc = "999999999999"
        dummy_data = {
            "variables": {
                "Test Item": {
                    "name": "Test Item",
                    "brand_name": "Test Brand",
                    "upc": dummy_upc,
                    "calories": 200,
                    "fat": 10.5,
                    "carbohydrates": 20.0,
                    "protein": 5.0,
                    "fiber": 3.5,
                    "sodium": 150.0,
                    "serving_size": "1 bar"
                }
            }
        }

        database.save_product_to_db(dummy_data)

        # Test Retrieval
        result = database.get_product_from_db(dummy_upc)
        self.assertIsNotNone(result, "Product not found in database")

        expected_values = {
            "fat_g": 10.5,
            "carbs_g": 20.0,
            "protein_g": 5.0,
            "fiber_g": 3.5,
            "sodium_mg": 150.0
        }

        for key, expected in expected_values.items():
            self.assertEqual(result.get(key), expected, f"{key} mismatch")

if __name__ == '__main__':
    unittest.main()
