#!/bin/bash

# Quick Visual Tests - Essential checks only
# For rapid development iterations

set -ex
echo "🚀 Running quick visual tests (essential checks only)..."

mkdir -p tests/examples
cd tests/examples

echo "🛡️  Testing blocking ..."
shot-power-scraper ../pages/ad-popup-test.html -o "blocking-BEFORE-shows-ads-and-popups.png" -w 800 -h 600
shot-power-scraper ../pages/ad-popup-test.html -o "blocking-AFTER-both-clean-content-only.png" --ad-block --popup-block -w 800 -h 600
shot-power-scraper cnn.com -o "EXTERNAL-blocking-cnn.jpg" --ad-block --popup-block --paywall-block --wait 3000

echo "🎯 Testing selectors..."
shot-power-scraper ../pages/complex-layout.html -o "selector-FULL-PAGE-everything-visible.png" -w 800 -h 600
shot-power-scraper ../pages/complex-layout.html -o "selector-HEADER-ONLY-blue-banner.png" -s "#main-header"

echo "⏱️  Testing timing..."
shot-power-scraper ../pages/timing-test.html -o "timing-NO-WAIT-missing-delayed-content.png" -w 600 -h 500
shot-power-scraper ../pages/timing-test.html -o "timing-WAIT-FOR-shows-all-content.png" --wait-for "document.getElementById('final-status') && getComputedStyle(document.getElementById('final-status')).display !== 'none'" -w 600 -h 500

echo "📄 Testing PDF..."
shot-power-scraper pdf ../pages/complex-layout.html -o "pdf-portrait-standard-layout.pdf"

echo "🌐 Testing external site (proves HTTP works)..."
shot-power-scraper https://eli.pizza/ -o "external-eli-pizza.png"

echo "📋 Testing multi-shot YAML..."
cat > multi-test.yaml << 'EOF'
- url: ../pages/ad-popup-test.html
  output: multi-LOCAL-FILE-with-ads.png
  width: 600
  height: 400
- url: https://eli.pizza/
  output: multi-EXTERNAL-SITE-elipizza.png
  width: 500
  height: 300
EOF
shot-power-scraper multi multi-test.yaml

echo "✅ Quick tests complete! Check key functionality:"
echo "🛡️  blocking-BEFORE vs blocking-AFTER (ads should disappear)"
echo "🎯 selector-FULL-PAGE vs selector-HEADER-ONLY (element isolation)"
echo "⏱️  timing-NO-WAIT vs timing-WAIT-FOR (delayed content)"
echo "📄 pdf-portrait-standard-layout.pdf (readable layout)"
echo "🌐 external-EXAMPLE-DOT-COM-basic-http.png (real HTTP site works)"
echo "📋 multi-LOCAL-FILE-with-ads.png & multi-EXTERNAL-SITE-example.png (YAML batch works)"
