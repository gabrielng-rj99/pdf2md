# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PDF-to-Markdown-with-Images** is a FastAPI web application that converts PDFs to Markdown while preserving:
- Formatted text with structure and styling
- Relevant images (with intelligent filtering to remove headers, footers, borders)
- Automatic reference detection ("Figure 1", "Table 3", etc.)
- Multilingual support (Portuguese and English)

## Common Commands

```bash
# Development
python run.py                    # Start development server on localhost:8000
make run                        # Same as above (via Makefile)
make dev                        # Alias for run

# Testing
pytest tests/unit tests/integration -v                    # Run all tests
pytest tests/unit -v                                      # Run unit tests only
pytest tests/integration -v                               # Run integration tests only
pytest --cov=app --cov-report=html                        # Run with coverage
pytest -k "test_name"                                     # Run specific test
python run_tests.py                                        # Alternative test runner

# Code Quality
make format    # Format with black
make lint      # Lint with pylint (errors/fatal only)

# Cleanup
make clean     # Remove cache and temp files
```

## Architecture

### Key Files
- `app/main.py` - FastAPI application with endpoints for PDF upload and download
- `app/services/pdf2md_service.py` - Core PDF processing logic using PyMuPDF
- `app/core/md_formatter.py` - Markdown formatting utilities
- `app/utils/` - Specialized utilities:
  - `image_filter.py` - Intelligent image filtering (removes headers, footers, borders, solid colors)
  - `heading_scorer.py` - Heading detection using multiple heuristics
  - `list_detector.py` - List structure detection
  - `text_cleaner.py` - Text cleanup and normalization

### API Endpoints
- `POST /api/upload/` - Upload single PDF, returns Markdown + images as ZIP
- `POST /api/upload-multiple/` - Upload multiple PDFs, returns consolidated ZIP
- `GET /api/download/{filename}` - Download generated Markdown
- `GET /api/download-zip/{filename}` - Download ZIP with Markdown + images
- `GET /api/health/` - Health check

### Processing Pipeline
1. PDF upload → PyMuPDF extraction
2. Text extraction with layout preservation
3. Image extraction with intelligent filtering:
   - Removes headers/footers (top/bottom 10% margins)
   - Removes small images in side margins (<50px width)
   - Removes tiny images (<3000px²)
   - Removes solid-color images (std dev <10)
   - Detects figure/table references in text
4. Heading detection via scoring heuristics
5. List structure detection
6. Markdown output generation

## Development Notes

- **Self-host only**: Not recommended for public production without authentication
- **Python 3.13** required
- **Environment**: Uses `.venv` virtual environment
- **Configuration**: `config.ini` for runtime settings, `config.py` for app constants
- **Frontend**: Simple HTML/JS in `frontend/` directory served by FastAPI
- **Docker**: `deploy/` contains Docker setup with nginx proxy and self-signed certificates

## Testing

The project uses pytest with markers defined in `pytest.ini`:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.filter` - Image filter tests
- `@pytest.mark.pdf` - PDF processing tests

## Orchestration Behavior

When working on tasks that span multiple areas/files:

1. **Always decompose into parallel subtasks** - Identify independent work streams
2. **Spawn agents concurrently** - Use Agent tool with appropriate subagent_type for each area
3. **Coordinate via TeamCreate** - For complex multi-file changes, create a team with shared task list
4. **Never work sequentially** - If N areas need work, do them in parallel, not one after another

### When to Orchestrate
- Multi-file refactoring across different modules
- Adding features that touch multiple layers (API, service, utils)
- Code reviews across several files
- Testing changes that affect multiple components
- Bug fixes that span multiple areas

### Example Pattern
```
Task: Update image filter and add tests
→ Spawn Agent 1: Update image filter logic
→ Spawn Agent 2: Add unit tests for image filter
→ Spawn Agent 3: Update integration tests
→ Wait for all to complete, then coordinate final changes
```
