# Use the official Puppeteer image, which is multi-arch and has a stock Chromium.
FROM ghcr.io/puppeteer/puppeteer:latest

# Set non-interactive frontend for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, pip, venv, and additional fonts for stealth.
# The Puppeteer image is Debian-based. These commands must run as root.
RUN apt-get update && \
    # Accept the EULA for Microsoft fonts first to prevent interactive prompts
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    fonts-noto-color-emoji \
    ttf-mscorefonts-installer && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory for the root user initially
WORKDIR /app

# The Puppeteer image creates a 'pptruser'. We will switch to it.
# Switch to the non-root user and set the working directory.
USER pptruser
WORKDIR /home/pptruser/app

# Copy dependency definition files
COPY --chown=pptruser:pptruser pyproject.toml uv.lock ./

# Install Python dependencies using uv into a virtual environment
# First, create the venv
RUN python3 -m venv .venv
# Activate the venv for subsequent commands
ENV PATH="/home/pptruser/app/.venv/bin:$PATH"
# Install uv using pip
RUN pip install uv
# Now, sync the environment using the lock file.
RUN uv sync --frozen

# Copy the application source code into the container
COPY --chown=pptruser:pptruser shot_power_scraper ./shot_power_scraper
COPY --chown=pptruser:pptruser main.py .

# Set the entrypoint to run the application's CLI.
ENTRYPOINT ["python3", "main.py"]
