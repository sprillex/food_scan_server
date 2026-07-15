# Food Scan Server

The Food Scan Server is a FastAPI-based backend application designed to process images of food labels, extract nutritional data using the Google Gemini AI API, and store this information in a local SQLite database for future retrieval.

## Prerequisites
- Python 3.10+
- `git`
- A Google Gemini API Key

## Environment Setup
1. Clone the repository and enter the directory.
2. Create a `.env` file in the root directory and add your API key:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

## Installation & Running Locally

### Development Server
To run the server locally for development:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Production Setup (Systemd)
The repository includes a `setup.sh` script to automate installing dependencies and configuring the application to run as a systemd service (`foodscan.service`).

```bash
chmod +x setup.sh
./setup.sh
```

## Systemd Service Management
Once installed via `setup.sh`, you can manage the server using standard `systemctl` commands:

- **Check Status:** `sudo systemctl status foodscan`
- **Restart Service:** `sudo systemctl restart foodscan`
- **Stop Service:** `sudo systemctl stop foodscan`
- **View Live Logs:** `sudo journalctl -u foodscan -f`
- **Application Logs:** The application also logs to `foodscan.log` in the root directory.

## API Endpoints

### 1. Analyze Image
- **Endpoint:** `POST /analyze`
- **Description:** Uploads an image of a food label. The server extracts the UPC and nutritional data using Gemini and saves it to the database.
- **Request:** `multipart/form-data` with a `file` field containing the image.
- **Response:** JSON containing the parsed nutritional data.

### 2. Get Product by UPC
- **Endpoint:** `GET /product/{upc}`
- **Description:** Checks the local SQLite database for a previously scanned UPC.
- **Response:**
  - If found: JSON object with product details.
  - If not found: `{"status": "not_found", "message": "Item unknown. Please scan label."}`

## Testing
To run the test suite, use the following command from the project root:
```bash
export PYTHONPATH=$PYTHONPATH:. && python3 -m unittest discover tests/
```