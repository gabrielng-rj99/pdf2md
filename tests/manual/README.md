# Manual Tests

This directory contains manual test scripts that require a running server or special setup.

## Scripts

### `test_download_zip.py`
Tests the ZIP download functionality with the real `aula1.pdf` file.

**Requirements:**
- `aula1.pdf` must exist in the project root
- The output directory must be writable

**Usage:**
```bash
python tests/manual/test_download_zip.py
```

### `test_multiple_pdfs.py`
Tests uploading and processing multiple PDFs.

**Requirements:**
- A running FastAPI server on `http://localhost:8000`
- At least 2 PDF files in the test directory

**Usage:**
```bash
# Start the server in one terminal:
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run the test in another terminal:
python tests/manual/test_multiple_pdfs.py
```

## Automated Tests

For automated testing, use pytest:

```bash
# Run all unit and integration tests
pytest tests/unit tests/integration -v

# Run with coverage
pytest tests/unit tests/integration -v --cov=app --cov-report=html

# Run specific test class
pytest tests/integration/test_api.py::TestEdgeCaseSamePdfName -v
```

## Test Coverage

Current test coverage:
- **Unit Tests:** 47 tests
- **Integration Tests:** 25 tests
- **Total:** 72 tests passing
- **Coverage:** 49%

### Coverage by Module
- `app/utils/image_filter.py`: 79%
- `app/main.py`: 64%
- `app/services/pdf2md_service.py`: 60%
- `app/utils/image_reference_mapper.py`: 30%
- `app/core/md_formatter.py`: 0%
- `app/config.py`: 0%
- `app/utils/helpers.py`: 0%

## Key Test Scenarios

### Edge Cases Covered

1. **Same PDF Name (Multiple Uploads)**
   - Test: `TestEdgeCaseSamePdfName::test_upload_same_pdf_name_twice`
   - Verifies that uploading the same PDF twice works correctly
   - Both uploads should generate files with the same base name

2. **Multiple Different PDFs with Same Name**
   - Test: `TestEdgeCaseSamePdfName::test_multiple_different_pdfs_same_base_name`
   - Uploads 3 different PDFs all named `report.pdf`
   - All should process successfully

3. **Real PDF Processing**
   - Test: `TestEndToEnd::test_full_workflow_with_real_aula_pdf`
   - Processes the real `aula1.pdf` file (80 pages)
   - Verifies Markdown and ZIP generation

### API Endpoints Tested

- `POST /api/upload/` - Single PDF upload
- `POST /api/upload-multiple/` - Multiple PDF upload
- `GET /api/download/{filename}` - Download Markdown
- `GET /api/download-zip/{filename}` - Download ZIP with images
- `GET /api/health/` - Health check

### Validation Tests

- PDF file validation
- Non-PDF file rejection
- File size validation
- Extension validation (uppercase, mixed case)
- Missing filename handling
- 404 handling for missing files
- CORS headers presence

## Running the Server

```bash
# Development mode with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000/api/`
The UI will be available at `http://localhost:8000/`

## Troubleshooting

### Permission Errors
If you get permission errors with the `output/` directory:
```bash
chmod -R 755 output/
```

### Module Not Found
Make sure dependencies are installed:
```bash
pip install -r requirements.txt
```

### PDF Processing Errors
Check that the PDF file is valid:
```bash
file aula1.pdf
```

## Notes

- All integration tests use temporary directories to avoid permission issues
- Tests are isolated and don't affect each other
- Manual tests are kept separate to avoid interfering with automated test runs
- The application uses PyMuPDF (fitz) for PDF processing
- Images are extracted and deduplicated based on MD5 hashes