# Testing Strategy

This directory contains tests for shot-power-scraper, organized for speed and reliability.

## Test Organization

### Quick Tests (Unit Tests)
- **`test_shot_config.py`** - Fast unit tests for ShotConfig functionality
- **`test_utils.py`** - Utility function tests
- **Run with:** `uv run python -m pytest -m quick`
- **Speed:** ~0.15s for all quick tests

### Integration Tests (Browser Required)
- **`test_shot_scraper.py`** - CLI command integration tests 
- **Run with:** `uv run python -m pytest -m browser_required`
- **Speed:** ~2-5s per test (requires browser)

### Visual Tests (Human Review Required)
- **`run_visual_tests.sh`** - Comprehensive visual examples for human inspection
- **`run_visual_tests_quick.sh`** - Essential visual tests only (faster)
- **Purpose:** Test visual output quality, ad/popup blocking effectiveness, layout accuracy
- **Speed:** ~30s (quick) to ~2min (full) - creates files for manual review

### Test Pages
- **`pages/`** - Local HTML files for reliable testing
  - `ad-popup-test.html` - Tests ad/popup blocking with obvious visual elements
  - `timing-test.html` - Tests wait/timing functionality with delayed content
  - `complex-layout.html` - Complex page for PDF, selectors, scaling tests
  - `simple.html` - Basic page with predictable dimensions
  - `lazy-loading.html` - Tests lazy loading functionality  
  - `pdf-test.html` - PDF generation features

## Running Tests

```bash
# Quick feedback - unit tests only (0.15s)
uv run python -m pytest -m quick

# Full automated test suite including browser tests
uv run python -m pytest

# Skip slow browser tests (good for CI without browser)
uv run python -m pytest -m "not browser_required"

# Run specific test
uv run python -m pytest tests/test_shot_config.py::TestShotConfig::test_scale_factor_retina_validation

# Visual tests - require human review of output files
./tests/run_visual_tests_quick.sh    # Essential visual checks (~30s)
./tests/run_visual_tests.sh          # Comprehensive visual tests (~2min)

# Visual regression tests - automated comparison to reference images
./tests/run_visual_regression.sh quick    # Compare quick tests to references
./tests/run_visual_regression.sh          # Compare full tests to references
```

## Test Focus Areas

### Automated Tests - Regression Protection
Tests are designed to catch bugs that have occurred before:

1. **Width/Height Parameters** - `test_screenshot_dimensions_regression()`
   - Verifies --width and --height actually affect output
   - Regression test for issue where parameters were ignored

2. **Selector Screenshots** - `test_selector_screenshot_regression()`
   - Tests element selection and timing
   - Verifies selector screenshots work with proper element detection

3. **Scale Factor Validation** - `test_scale_factor_retina_validation()`
   - Tests retina/scale-factor conflict detection
   - Ensures validation works at ShotConfig level

4. **Architecture Changes** - Various tests
   - Tests new create_tab_context + navigate_to_url pattern
   - Ensures ShotConfig creation with locals() works

### Visual Tests - Human Review Required
Strategic tests with descriptive filenames for visual verification:

1. **Extension Blocking** - `blocking-BEFORE-*` vs `blocking-AFTER-*`
   - Tests ad/popup blocking effectiveness (major missing coverage)
   - Before/after comparisons make issues immediately obvious

2. **Selector Precision** - `selector-*-ONLY-*` files
   - Verifies exact element targeting works correctly
   - Tests single vs multiple selector behavior

3. **Timing Behavior** - `timing-*` comparison files
   - Tests wait vs no-wait scenarios
   - Validates delayed content handling

4. **PDF Quality** - `pdf-*-layout.pdf` files
   - Tests portrait vs landscape orientation
   - Validates scaling and formatting

5. **Visual Quality** - `quality-*` comparison files
   - Tests retina vs standard scaling
   - JPEG compression and transparency

### Visual Regression Testing (Automated)
Automated comparison against reference images to catch visual regressions:

**Setup Workflow:**
1. Run initial baseline: `./tests/run_visual_tests_quick.sh`
2. Save as references: `cp tests/examples/*.{png,jpg,pdf} tests/references/`
3. Run regression tests: `./tests/run_visual_regression.sh quick`

**Directory Structure:**
- `tests/examples/` - Current test outputs
- `tests/references/` - "Golden" reference images  
- `tests/diffs/` - Generated diff images (red highlights show changes)

**Usage:**
- `./tests/run_visual_regression.sh quick` - Fast regression check (~45s)
- `./tests/run_visual_regression.sh` - Full regression check (~3min)  
- Exit code 0 = all tests pass, >0 = number of visual regressions detected

**Tolerance:** Allows up to 100 different pixels per image (configurable in script)

### Core Functionality (Automated)
- PDF generation (basic validation)
- JavaScript execution
- Multi-shot YAML processing
- Configuration file handling

## Design Principles

Following CLAUDE.md guidelines:

- **No Fallbacks** - Tests fail fast and loud when things break
- **Strategic Testing** - Focus on core functionality, not every edge case
- **Speed Grouping** - Quick tests for immediate feedback, slower tests for full validation
- **Local Test Pages** - Reliable, predictable test content instead of external sites
- **Regression Focus** - Tests that would have caught recent bugs

## Dependencies

- **Quick tests** - No external dependencies
- **Browser tests** - Require working browser (skipped in CI)
- **Image validation** - Uses file size checks instead of requiring PIL
- **PDF validation** - Uses file size checks instead of requiring PyMuPDF