import base64
import nodriver as uc


# Standard paper sizes in inches
PAPER_SIZES = {
    "letter": (8.5, 11),
    "legal": (8.5, 14),
    "tabloid": (11, 17),
    "ledger": (17, 11),
    "a0": (33.1, 46.8),
    "a1": (23.4, 33.1),
    "a2": (16.5, 23.4),
    "a3": (11.7, 16.5),
    "a4": (8.27, 11.7),
    "a5": (5.83, 8.27),
    "a6": (4.13, 5.83),
}


def parse_dimension(dimension_str):
    """Parse a dimension string like '10cm' or '5in' and return inches."""
    if not dimension_str:
        return None
    
    dimension_str = dimension_str.strip().lower()
    
    # Handle common units
    if dimension_str.endswith('cm'):
        return float(dimension_str[:-2]) / 2.54  # Convert cm to inches
    elif dimension_str.endswith('mm'):
        return float(dimension_str[:-2]) / 25.4  # Convert mm to inches
    elif dimension_str.endswith('in'):
        return float(dimension_str[:-2])
    elif dimension_str.endswith('px'):
        return float(dimension_str[:-2]) / 96  # Assume 96 DPI
    else:
        # Assume inches if no unit specified
        return float(dimension_str)


async def generate_pdf(page, options):
    """Generate PDF from a page using Chrome DevTools Protocol."""
    
    # Build CDP print options
    print_options = {
        "landscape": options.get("landscape", False),
        "display_header_footer": False,
        "print_background": options.get("print_background", True),
        "scale": options.get("scale", 1.0),
        "margin_top": 0.4,
        "margin_bottom": 0.4,
        "margin_left": 0.4,
        "margin_right": 0.4,
    }
    
    # Handle paper size
    format_ = options.get("format")
    width = options.get("width")
    height = options.get("height")
    
    if format_:
        # Use standard paper size
        paper_size = PAPER_SIZES.get(format_.lower())
        if paper_size:
            if options.get("landscape"):
                print_options["paper_height"] = paper_size[0]
                print_options["paper_width"] = paper_size[1]
            else:
                print_options["paper_width"] = paper_size[0]
                print_options["paper_height"] = paper_size[1]
    elif width or height:
        # Use custom dimensions
        if width:
            print_options["paper_width"] = parse_dimension(width)
        if height:
            print_options["paper_height"] = parse_dimension(height)
    else:
        # Default to A4
        print_options["paper_width"] = 8.27
        print_options["paper_height"] = 11.69
    
    # Handle media type
    if options.get("media_screen"):
        # Emulate screen media for CSS
        await page.send(uc.cdp.emulation.set_emulated_media(media="screen"))
    else:
        # Use print media (default)
        await page.send(uc.cdp.emulation.set_emulated_media(media="print"))
    
    # Generate PDF using CDP
    result = await page.send(uc.cdp.page.print_to_pdf(**print_options))
    
    # nodriver returns a tuple: (base64_string, stream_handle)
    # The first element is the base64-encoded PDF data as a string
    pdf_base64_string = result[0]
    
    # Decode base64 PDF data
    pdf_data = base64.b64decode(pdf_base64_string)
    
    return pdf_data