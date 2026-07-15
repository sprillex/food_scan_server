# Codebase Audit Report

## Executive Summary
The project is a FastAPI backend designed to process images of food labels, extract nutritional data using the Google Gemini API, and store the information in a local SQLite database. While the architecture separates concerns logically and handles blocking I/O using asynchronous threads, it currently lacks production-readiness. The audit identified several critical security, stability, and resource management issues, alongside significant gaps in documentation and missing functionality that existing tests expect.

## Critical Issues

1. **Unbounded Storage Growth (Resource Exhaustion)** - **[RESOLVED]**
   - **Location:** `server.py` (`/analyze` endpoint)
   - **Problem:** Every time an image is uploaded, a new directory (`images/scan_{uuid}`) is created and the image is saved. There is no mechanism to clean up or delete these files after processing. This will inevitably lead to disk space exhaustion.
   - **Fix Strategy:** Implemented `cleanup_image_directory` as a FastAPI `BackgroundTask` to securely delete the temporary files and folder once the Gemini analysis is complete.

2. **Missing API Retry Logic** - **[RESOLVED]**
   - **Location:** `server.py` (`analyze_evidence`)
   - **Problem:** The test suite includes `tests/test_retry_logic.py`, which explicitly tests for the presence of a retry loop with exponential backoff when the Gemini API returns an HTTP 429 (Too Many Requests) error. However, `server.py` does not currently implement any retry logic, causing transient errors to immediately fail the request.
   - **Fix Strategy:** Implemented an asynchronous retry loop around the `client.models.generate_content` call, catching `ClientError`, verifying the 429 status code, and using `asyncio.sleep` with backoff before retrying (up to 3 attempts).

3. **Missing File Size Validation** - **[RESOLVED]**
   - **Location:** `server.py` (`/analyze` endpoint)
   - **Problem:** The endpoint accepts file uploads without verifying the file size. Malicious actors or erroneous clients could upload massive files, causing memory exhaustion (OOM) or rapid disk depletion (Denial of Service).
   - **Fix Strategy:** Implemented a size check by reading the uploaded file in chunks. If the file exceeds the 5MB limit, it raises an HTTP 413 "Payload Too Large" error before proceeding to save or analyze it.

## Documentation Audit

1. **Empty README.md** - **[RESOLVED]**
   - **Location:** `README.md`
   - **Problem:** The README currently only contains the project title (`# food_scan_server`).
   - **Fix Strategy:** Updated the README to include a project description, setup instructions, API endpoint documentation, and testing instructions.

2. **Missing Systemd Configuration Documentation** - **[RESOLVED]**
   - **Location:** `foodscan.service`, `setup.sh`
   - **Problem:** The setup scripts automate service deployment, but there's no documentation explaining how to view logs or manage the service manually.
   - **Fix Strategy:** Added a dedicated "Systemd Service Management" section to the README detailing `systemctl` and `journalctl` commands.

## Optimization Suggestions

1. **Git Tree Pollution in `setup.sh`** - **[RESOLVED]**
   - **Location:** `setup.sh`
   - **Problem:** The setup script modifies `foodscan.service` in place using `sed`. This leaves untracked/modified files in the local Git repository, which can cause issues during updates (e.g., git pull conflicts).
   - **Fix Strategy:** Modified the script to create a temporary copy of the service file at `/tmp/foodscan.service`, applied the `sed` transformations there, moved it to `/etc/systemd/system/`, ensuring the git working directory remains clean.

2. **Missing CORS Configuration** - **[POSTPONED]**
   - **Location:** `server.py`
   - **Problem:** FastAPI does not have Cross-Origin Resource Sharing (CORS) configured. If a web frontend attempts to call this API, the browser will block the requests.
   - **Fix Strategy:** User opted to postpone this for a future update. While configuring `CORSMiddleware` is necessary for web apps, blindly allowing all origins (`*`) could lead to quota exhaustion via malicious sites. It will be implemented securely with specific allowed origins when a web frontend is built.

## Best Practices

1. **Environment Variable Validation on Startup**
   - **Location:** `server.py`
   - **Problem:** `GEMINI_API_KEY` is loaded but not validated. If it's missing, the app continues to start up and only fails when the API is called.
   - **Fix Strategy:** Add an explicit check during startup to raise an exception or log a critical error if the API key is not found in the environment.

2. **Database Connection Pooling**
   - **Location:** `database.py`
   - **Problem:** `get_product_from_db` and `save_product_to_db` open and close a new SQLite database connection for every request.
   - **Fix Strategy:** While SQLite is lightweight, implementing a persistent connection or connection pool pattern would improve throughput under higher load.
