#!/bin/bash

# Visual Regression Testing for shot-power-scraper
# Runs visual tests and compares against reference images using ImageMagick

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$SCRIPT_DIR/examples"
REFERENCES_DIR="$SCRIPT_DIR/references"
DIFFS_DIR="$SCRIPT_DIR/diffs"

# Create directories if they don't exist
mkdir -p "$REFERENCES_DIR" "$DIFFS_DIR"

echo "🔍 Running visual regression tests..."

# Allow choosing which test suite to run
if [[ "$1" == "quick" ]]; then
    echo "🚀 Running quick visual tests..."
    "$SCRIPT_DIR/run_visual_tests_quick.sh"
else
    echo "🧪 Running full visual tests..."
    "$SCRIPT_DIR/run_visual_tests.sh"
fi

echo ""
echo "📊 Comparing results to reference images..."

FAILURES=0
NEW_FILES=0
PASSED=0
TOLERANCE=100  # Allow up to 100 different pixels (adjust as needed)

# Compare all generated images
for current in "$EXAMPLES_DIR"/*.png "$EXAMPLES_DIR"/*.jpg; do
    [[ -f "$current" ]] || continue  # Skip if no files match

    filename=$(basename "$current")
    reference="$REFERENCES_DIR/$filename"
    diff_image="$DIFFS_DIR/${filename%.*}_diff.png"

    if [[ -f "$reference" ]]; then
        # Compare images - capture both stdout and stderr
        diff_output=$(compare -metric AE "$reference" "$current" null: 2>&1) || true

        # Extract the first number from output (handles scientific notation)
        # Output format is like "2.34399e+09 (35767)" or just "0"
        if [[ -n "$diff_output" ]]; then
            # Extract first word/number from output and convert scientific notation
            first_number=$(echo "$diff_output" | awk '{print $1}')
            # Use printf to convert scientific notation to integer
            diff_pixels=$(printf "%.0f" "$first_number" 2>/dev/null) || diff_pixels=999999
        else
            diff_pixels=999999  # Treat empty output as major difference
        fi

        if [[ $diff_pixels -gt $TOLERANCE ]]; then
            echo "❌ REGRESSION: $filename ($diff_pixels pixels different, tolerance: $TOLERANCE)"

            # Generate visual diff image (red highlights differences)
            compare "$reference" "$current" -compose src "$diff_image" 2>/dev/null || {
                echo "   (Could not generate diff image - images may be different sizes)"
            }

            FAILURES=$((FAILURES + 1))
        else
            echo "✅ PASS: $filename ($diff_pixels pixels different)"
            PASSED=$((PASSED + 1))
        fi
    else
        echo "⚠️  NEW: $filename (no reference image)"
        echo "   To make this the reference: cp '$current' '$reference'"
        NEW_FILES=$((NEW_FILES + 1))
    fi
done

# Check PDFs exist (can't easily diff them)
for current in "$EXAMPLES_DIR"/*.pdf; do
    [[ -f "$current" ]] || continue
    filename=$(basename "$current")
    reference="$REFERENCES_DIR/$filename"

    if [[ -f "$reference" ]]; then
        # Just check if PDF was created and has reasonable size
        current_size=$(stat -f%z "$current" 2>/dev/null || stat -c%s "$current" 2>/dev/null || echo 0)
        reference_size=$(stat -f%z "$reference" 2>/dev/null || stat -c%s "$reference" 2>/dev/null || echo 0)

        # Allow 20% size difference for PDFs
        size_diff=$(( (current_size - reference_size) * 100 / reference_size ))
        size_diff=${size_diff#-}  # absolute value

        if [[ $size_diff -gt 20 ]]; then
            echo "⚠️  PDF SIZE: $filename (${size_diff}% size difference)"
        else
            echo "✅ PDF: $filename (size within 20%)"
            PASSED=$((PASSED + 1))
        fi
    else
        echo "⚠️  NEW PDF: $filename"
        echo "   To make this the reference: cp '$current' '$reference'"
        NEW_FILES=$((NEW_FILES + 1))
    fi
done

echo ""
echo "📋 SUMMARY:"
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILURES"
echo "⚠️  New files: $NEW_FILES"

if [[ $NEW_FILES -gt 0 ]]; then
    echo ""
    echo "💡 To accept all new files as references:"
    echo "   cp tests/examples/*.{png,jpg,pdf} tests/references/ 2>/dev/null || true"
fi

if [[ $FAILURES -gt 0 ]]; then
    echo ""
    echo "🔍 Review diff images in: $DIFFS_DIR"
    echo "🖼️  View diffs: open '$DIFFS_DIR'"
    echo ""
    echo "💡 To update failing references (if changes are intentional):"
    echo "   # Review the diffs first, then:"
    echo "   cp tests/examples/failing-file.png tests/references/"
    echo "   # or all at once:"
    echo "   cp tests/examples/*.{png,pdf,jpg,json} tests/references/"
fi

echo ""
echo "📁 Files:"
echo "   Current results: $EXAMPLES_DIR"
echo "   Reference images: $REFERENCES_DIR"
echo "   Diff images: $DIFFS_DIR"

exit $FAILURES
