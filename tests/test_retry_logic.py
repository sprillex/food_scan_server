import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch, AsyncMock

# Mock database before importing server
sys.modules['database'] = MagicMock()

# Set dummy API key
os.environ["GEMINI_API_KEY"] = "fake_key"

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai.errors import ClientError
import server

class TestRetryLogic(unittest.IsolatedAsyncioTestCase):

    async def test_analyze_evidence_retry_success(self):
        # Setup mocks
        mock_generate_content = MagicMock()
        server.client.models.generate_content = mock_generate_content

        # Define side effect: 429 twice, then success
        error_429 = ClientError(code=429, response_json={}, response=None)

        success_response = MagicMock()
        success_response.text = '```json\n{"variables": {"Test Item": {"upc": "12345", "name": "Test", "calories": 100}}}\n```'

        mock_generate_content.side_effect = [error_429, error_429, success_response]

        # Mock UploadFile
        mock_file = MagicMock()
        mock_file.filename = "test.jpg"

        # Patch open to avoid file system ops
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"fake_image_data")), \
             patch("server.validate_and_save_image", return_value=None), \
             patch("os.makedirs"), \
             patch("os.path.exists", return_value=True):

            # Patch asyncio.sleep to check if it was called and avoid waiting
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

                result = await server.analyze_evidence(file=mock_file)

                # Assertions
                self.assertEqual(result['status'], 'success')
                self.assertEqual(mock_generate_content.call_count, 3)
                self.assertEqual(mock_sleep.call_count, 2)

    async def test_analyze_evidence_retry_fail(self):
         # Setup mocks
        mock_generate_content = MagicMock()
        server.client.models.generate_content = mock_generate_content

        # Define side effect: 429 always
        error_429 = ClientError(code=429, response_json={}, response=None)
        mock_generate_content.side_effect = error_429

        # Mock UploadFile
        mock_file = MagicMock()
        mock_file.filename = "test.jpg"

        with patch("builtins.open", unittest.mock.mock_open(read_data=b"fake_image_data")), \
             patch("server.validate_and_save_image", return_value=None), \
             patch("os.makedirs"), \
             patch("os.path.exists", return_value=True):

             with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:

                 result = await server.analyze_evidence(file=mock_file)

                 # Assertions
                 self.assertEqual(result['status'], 'error')
                 # Should try 3 times
                 self.assertEqual(mock_generate_content.call_count, 3)
                 self.assertEqual(mock_sleep.call_count, 2)

                 # Verify error message
                 # ClientError str includes code and message usually
                 self.assertIn("429", result['message'])

if __name__ == '__main__':
    unittest.main()
