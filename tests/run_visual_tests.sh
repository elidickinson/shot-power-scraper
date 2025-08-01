#!/bin/bash

# Strategic Visual Tests for shot-power-scraper
# Creates examples with descriptive names for human inspection
# Focus: Quality over quantity - test key functionality and edge cases

set -ex
echo "🧪 Running strategic visual tests..."

# Clean up and prepare
mkdir -p tests/examples
cd tests/examples
rm -f *.png *.pdf *.jpg *.html *.json 2>/dev/null || true

echo "📋 Creating test results with descriptive names for human review..."

# =============================================================================
# 🛡️  EXTENSION BLOCKING TESTS (Major missing functionality)
# =============================================================================
echo "🛡️  Testing ad/popup blocking effectiveness..."

# Before/after comparison
shot-power-scraper ../pages/ad-popup-test.html \
  -o "blocking-BEFORE-shows-ads-and-popups.png" \
  -w 800 -h 600

shot-power-scraper ../pages/ad-popup-test.html \
  -o "blocking-AFTER-ad-block-removes-ads.png" \
  --ad-block -w 800 -h 600

shot-power-scraper ../pages/ad-popup-test.html \
  -o "blocking-AFTER-popup-block-removes-popups.png" \
  --popup-block -w 800 -h 600

shot-power-scraper ../pages/ad-popup-test.html \
  -o "blocking-AFTER-both-clean-content-only.png" \
  --ad-block --popup-block -w 800 -h 600

shot-power-scraper cnn.com -o "EXTERNAL-blocking-cnn.jpg" --ad-block --popup-block --paywall-block --wait 3000

# =============================================================================
# 📄 PDF GENERATION TESTS
# =============================================================================
echo "📄 Testing PDF generation variants..."

shot-power-scraper pdf ../pages/complex-layout.html \
  -o "pdf-portrait-standard-layout.pdf"

shot-power-scraper pdf ../pages/complex-layout.html \
  -o "pdf-landscape-wide-layout.pdf" \
  --landscape

shot-power-scraper pdf ../pages/complex-layout.html \
  -o "pdf-scaled-smaller-text.pdf" \
  --scale 0.7

# =============================================================================
# 📦 MHTML ARCHIVE TESTS
# =============================================================================
echo "📦 Testing MHTML web archive generation..."

# Basic MHTML capture
shot-power-scraper mhtml ../pages/complex-layout.html \
  -o "mhtml-basic-complete-archive.mhtml"

# MHTML with ad blocking
shot-power-scraper mhtml ../pages/ad-popup-test.html \
  -o "mhtml-with-ad-blocking.mhtml" \
  --ad-block --popup-block

# MHTML with JavaScript execution
shot-power-scraper mhtml ../pages/complex-layout.html \
  -o "mhtml-with-javascript.mhtml" \
  --javascript "document.body.style.backgroundColor='#f0f8ff'"

# MHTML with lazy loading trigger
shot-power-scraper mhtml ../pages/lazy-loading.html \
  -o "mhtml-with-lazy-load.mhtml" \
  --trigger-lazy-load

# External site MHTML
shot-power-scraper mhtml https://eli.pizza/ \
  -o "mhtml-external-site.mhtml"

# =============================================================================
# 🎯 SELECTOR PRECISION TESTS
# =============================================================================
echo "🎯 Testing element selection accuracy..."

# Full page vs specific elements
shot-power-scraper ../pages/complex-layout.html \
  -o "selector-FULL-PAGE-everything-visible.png" \
  -w 1000 -h 800

shot-power-scraper ../pages/complex-layout.html \
  -o "selector-HEADER-ONLY-blue-banner.png" \
  -s "#main-header"

shot-power-scraper ../pages/complex-layout.html \
  -o "selector-SIDEBAR-ONLY-gray-navigation.png" \
  -s "#test-sidebar"

shot-power-scraper ../pages/complex-layout.html \
  -o "selector-TABLE-ONLY-with-data.png" \
  -s "#data-table" --padding 10

# Multiple selectors
shot-power-scraper ../pages/complex-layout.html \
  -o "selector-HEADER-AND-SIDEBAR-combined.png" \
  -s "#main-header" -s "#test-sidebar" --padding 15

# =============================================================================
# ⏱️  TIMING AND WAIT TESTS
# =============================================================================
echo "⏱️  Testing timing behavior..."

# No wait - should miss delayed content
shot-power-scraper ../pages/timing-test.html \
  -o "timing-NO-WAIT-missing-delayed-content.png" \
  -w 600 -h 500

# Wait for specific element
shot-power-scraper ../pages/timing-test.html \
  -o "timing-WAIT-FOR-shows-all-content.png" \
  --wait-for "document.getElementById('final-status') && getComputedStyle(document.getElementById('final-status')).display !== 'none'" \
  -w 600 -h 500

# Fixed wait
shot-power-scraper ../pages/timing-test.html \
  -o "timing-WAIT-3SEC-shows-final-status.png" \
  --wait 3500 -w 600 -h 500

# =============================================================================
# 🎨 VISUAL QUALITY TESTS
# =============================================================================
echo "🎨 Testing visual quality options..."

# Scale factor comparison
shot-power-scraper ../pages/complex-layout.html \
  -o "quality-STANDARD-1x-scale.png" \
  -w 400 -h 300

shot-power-scraper ../pages/complex-layout.html \
  -o "quality-RETINA-2x-sharper.png" \
  --retina -w 400 -h 300

# JPEG quality
shot-power-scraper ../pages/complex-layout.html \
  -o "quality-JPEG-80-compressed.jpg" \
  --quality 80 -w 400 -h 300

# Background transparency
shot-power-scraper ../pages/complex-layout.html \
  -o "quality-TRANSPARENT-background.png" \
  --omit-background \
  --javascript "document.body.style.backgroundColor='transparent'" \
  -w 400 -h 300

# =============================================================================
# 🔧 CORE FUNCTIONALITY TESTS
# =============================================================================
echo "🔧 Testing core functionality..."

# Local file handling
echo '<html><body style="background:#e8f5e8;padding:20px;"><h1>📁 Local File Test</h1><p>This file was loaded from disk, not a URL.</p></body></html>' > local-test.html
shot-power-scraper local-test.html \
  -o "core-LOCAL-FILE-from-disk.png"

# Dimensions and viewport
shot-power-scraper https://eli.pizza \
  -o "core-CUSTOM-DIMENSIONS-800x400.png" \
  -w 800 -h 400

# JavaScript execution
shot-power-scraper ../pages/complex-layout.html \
  -o "core-JAVASCRIPT-pink-background.png" \
  --javascript "document.body.style.backgroundColor='#ff69b4'" \
  -w 500 -h 400

# =============================================================================
# ⚠️  EDGE CASE TESTS
# =============================================================================
echo "⚠️  Testing edge cases and error handling..."

# Non-existent selector (should throw error)
if shot-power-scraper ../pages/complex-layout.html \
  -o "edge-MISSING-SELECTOR-SHOULD-NOT-EXIST.png" \
  -s "#does-not-exist" -w 500 -h 400 2>/dev/null; then
  echo "❌ edge-MISSING-SELECTOR: Expected non-zero exit code, but got zero."
else
  echo "✅ edge-MISSING-SELECTOR: Correctly returned non-zero exit code for missing selector."
fi

# Very small dimensions
shot-power-scraper ../pages/complex-layout.html \
  -o "edge-TINY-200x150-dimensions.png" \
  -w 200 -h 150

# =============================================================================
# 📊 CONSOLE AND DEBUG TESTS
# =============================================================================
echo "📊 Testing console logging and debug features..."

# Console logging (check terminal output)
shot-power-scraper ../pages/timing-test.html \
  -o "debug-WITH-CONSOLE-logging.png" \
  --log-console -w 500 -h 400

# JavaScript execution with output
shot-power-scraper javascript ../pages/complex-layout.html \
  "document.title + ' - ' + document.querySelectorAll('h2').length + ' sections'" \
  > debug-javascript-output.json

# =============================================================================
# 🌐 EXTERNAL SITE TESTS (Prove real-world functionality)
# =============================================================================
echo "🌐 Testing external sites (proves HTTP/HTTPS works)..."

# Basic HTTP functionality
shot-power-scraper https://eli.pizza/ -o "external-eli-pizza.png"

# Real-world complex site
shot-power-scraper https://github.com \
  -o "external-GITHUB-complex-site.png" \
  -w 1000 -h 800

# HTTPS with custom selector (proves real-world selector usage)
shot-power-scraper https://github.com \
  -o "external-GITHUB-HEADER-ONLY-navigation.png" \
  -s "header" --padding 10

# =============================================================================
# 📋 MULTI-SHOT YAML TESTS (Batch processing)
# =============================================================================
echo "📋 Testing multi-shot YAML functionality..."

# Comprehensive multi test with mixed features
cat > multi-comprehensive.yaml << 'EOF'
# Local file with selector
- url: ../pages/complex-layout.html
  output: multi-LOCAL-with-selector-header.png
  selector: "#main-header"
  width: 800
  height: 200

# External site with custom dimensions
- url: https://eli.pizza/
  output: multi-EXTERNAL-SITE-elipizza.png
  width: 500
  height: 300

# PDF generation in multi
- url: ../pages/complex-layout.html
  output: multi-PDF-from-yaml.pdf
  format: pdf

# Timing test in multi
- url: ../pages/timing-test.html
  output: multi-TIMING-with-wait.png
  wait_for: "document.getElementById('final-status') && getComputedStyle(document.getElementById('final-status')).display !== 'none'"
  width: 500
  height: 400

# JavaScript in multi
- url: ../pages/complex-layout.html
  output: multi-JAVASCRIPT-pink-background.png
  javascript: "document.body.style.backgroundColor='#ff69b4'"
  width: 500
  height: 300
EOF

shot-power-scraper multi multi-comprehensive.yaml

echo "✅ Visual tests complete!"
echo ""
echo "📋 REVIEW CHECKLIST:"
echo "🛡️  Blocking: Compare BEFORE vs AFTER - ads/popups should disappear"
echo "📄 PDFs: Check portrait vs landscape orientation"
echo "📦 MHTML: Archives should contain complete pages with resources (view in browser)"
echo "🎯 Selectors: Verify only targeted elements are captured"
echo "⏱️  Timing: NO-WAIT should miss content, others should show it"
echo "🎨 Quality: RETINA should be sharper, JPEG smaller file"
echo "🔧 Core: Custom dimensions should be exact size"
echo "⚠️  Edge: MISSING-SELECTOR should fallback gracefully"
echo "🌐 External: Sites should load properly, GitHub header should be isolated"
echo "📋 Multi: All 5 multi-* files should exist with expected content/formats"
echo ""
echo "Files saved to: tests/examples/"
echo "View with: open tests/examples/"
