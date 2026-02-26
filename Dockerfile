# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-traditional \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Tailwind CSS Standalone CLI
RUN curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 && \
    chmod +x tailwindcss-linux-x64 && \
    mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright Chromium and system dependencies (for voting place query headless)
RUN python -m playwright install --with-deps chromium

# Copy project files needed for Tailwind compilation first (for better caching)
COPY tailwind.config.js /app/
COPY static/css/input.css /app/static/css/

# Compile Tailwind CSS (before copying all files to speed up rebuilds)
RUN mkdir -p /app/static/css && \
    tailwindcss -i /app/static/css/input.css -o /app/static/css/output.css --minify

# Copy rest of project
COPY . /app/

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Copy supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create static and media directories
RUN mkdir -p /app/staticfiles /app/media

# Make entrypoint script executable
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Expose port 80
EXPOSE 80

# Run entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
