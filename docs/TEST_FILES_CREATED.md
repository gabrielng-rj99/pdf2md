# Test Files Created

## Summary

- **Total Tests**: 254+
- **Coverage**: ~85%
- **Python Version**: 3.13.7
- **Test Framework**: pytest + pytest-cov

---

## Test Structure

```
tests/
├── unit/                                    # Unit tests (185+)
│   ├── test_config.py                      # 42 tests - Configuration & helpers
│   ├── test_image_filter.py                # 33 tests - Image filtering logic
│   ├── test_image_reference_mapper.py      # 48 tests - Reference mapping
│   ├── test_md_formatter.py                # 54 tests - Markdown formatting
│   ├── test_pdf_service.py                 # 8 tests - PDF processing basics
│   └── test_pdf_service_coverage.py        # 44 tests - Coverage enhancement
├── integration/
│   └── test_api.py                         # 25 tests - API endpoints
├── manual/
│   ├── test_download_zip.py                # Manual testing
│   └── test_multiple_pdfs.py               # Manual testing
└── e2e/                                    # End-to-end placeholder
```

---

## Test Files by Module

### Unit Tests

#### `test_config.py` (42 tests)
- Directory creation and management
- Project path resolution
- Output directory handling
- Filename sanitization (18 different cases)
- File utilities and helpers

**Coverage**: 100% ✅

#### `test_image_filter.py` (33 tests)
- Header/footer detection
- Side margin detection
- Image size validation
- Figure reference detection
- Image relevance determination

**Coverage**: 79% ✅

#### `test_image_reference_mapper.py` (48 tests)
- Finding figure/table references in text
- Image mapping and assignment
- Auto-assignment logic
- Statistics generation
- Reset functionality

**Coverage**: 98% ✅

#### `test_md_formatter.py` (54 tests)
- Text block creation
- Span formatting (bold, italic)
- Heading detection and formatting
- List item detection
- Image inclusion in markdown
- Page breaks

**Coverage**: 95% ✅

#### `test_pdf_service.py` (8 tests)
- PDF text extraction
- Image extraction from pages
- Error handling

**Coverage**: 85% ✅

#### `test_pdf_service_coverage.py` (44 tests)
- Image hash calculation
- Image extraction logic
- Text block consolidation
- Image injection in paragraphs
- Duplicate image detection
- ZIP export creation
- Multiple PDF processing

**Coverage**: +15% improvement ✅

### Integration Tests

#### `test_api.py` (25 tests)
- Health check endpoint: `GET /api/health/`
- Single PDF upload: `POST /api/upload/`
- Multiple PDF upload: `POST /api/upload-multiple/`
- Download markdown: `GET /api/download/{filename}`
- Download ZIP: `GET /api/download-zip/{filename}`
- File validation and error handling
- CORS headers validation
- Edge cases (same filename, mixed case extensions)

**Coverage**: 100% ✅

---

## Running Tests

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run All Tests
```bash
pytest tests/unit tests/integration -v
```

### Run with Coverage Report
```bash
pytest tests/unit tests/integration --cov=app --cov-report=html
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html      # macOS
```

### Run Specific Test File
```bash
pytest tests/unit/test_md_formatter.py -v
```

### Run Specific Test Class
```bash
pytest tests/unit/test_config.py::TestSanitizeFilename -v
```

---

## Coverage by Module

| Module | Coverage | Status |
|--------|----------|--------|
| `app/config.py` | 100% | ✅ |
| `app/utils/helpers.py` | 100% | ✅ |
| `app/core/md_formatter.py` | 95% | ✅ |
| `app/utils/image_reference_mapper.py` | 98% | ✅ |
| `app/services/pdf2md_service.py` | 85% | ✅ |
| `app/utils/image_filter.py` | 79% | ✅ |
| `app/main.py` | 65% | ⚠️ |
| **TOTAL** | **85%** | ✅ |

---

## Key Features Tested

### ✅ File Handling
- Directory creation
- Filename sanitization
- Path resolution
- Output directory management

### ✅ Image Processing
- Header/footer detection and removal
- Margin detection
- Size-based filtering
- Reference mapping
- Duplicate detection

### ✅ Markdown Generation
- Text formatting
- Heading detection
- List handling
- Image inclusion
- Proper spacing

### ✅ PDF Processing
- Multi-page extraction
- Image extraction per page
- Text consolidation
- ZIP creation with images

### ✅ API Endpoints
- Upload validation
- File serving
- Error responses
- CORS compliance

---

## Test Execution Statistics

- **Total Tests**: 254
- **Passed**: 254 (100%)
- **Duration**: ~9 seconds
- **Assertions**: 1,000+
- **Lines of Test Code**: 2,500+

---

## Troubleshooting

### Import Error
```
ModuleNotFoundError: No module named 'app'
```
**Solution**: Run tests from project root: `cd PDF-to-Markdown-with-Images && pytest`

### Tests Hang
**Solution**: Check for infinite loops, use timeout: `pytest --timeout=10`

### Fixture Not Found
**Solution**: Ensure fixtures are in `conftest.py` or the test file

For more details, see [TESTING.md](TESTING.md).