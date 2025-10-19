#!/bin/bash

# Check if the input image exists
if [ ! -f "cwg.png" ]; then
    echo "Error: cwg.png not found." >&2
    exit 1
fi

# Check if the crop parameters file exists
if [ ! -f "crop_params.txt" ]; then
    echo "Error: crop_params.txt not found. Please create a file with crop parameters (x,y,width,height per line)." >&2
    exit 1
fi

# Initialize counter for output filenames
index=1

# Process each line in the crop parameters file
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip empty lines
    if [ -z "$line" ]; then
        continue
    fi

    # Split the line into x, y, width, height
    IFS=',' read -ra params <<< "$line"

    # Validate parameter count
    if [ ${#params[@]} -ne 4 ]; then
        echo "Warning: Invalid line '$line'. Skipping." >&2
        continue
    fi

    # Extract parameters
    x="${params[0]}"
    y="${params[1]}"
    width="${params[2]}"
    height="${params[3]}"

    # Create output filename
    output="post_$(printf "%02d" $index).png"

    # Perform the crop operation
    convert "cwg.png" -crop "${width}x${height}+${x}+${y}" +repage "$output"

    echo "Created $output"

    # Increment counter
    ((index++))
done < "crop_params.txt"

echo "All posts extracted successfully."