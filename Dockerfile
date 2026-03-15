FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY index.html .
COPY manifest.json .
COPY service-worker.js .
COPY entrypoint.sh .
COPY start.py .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/status').read()" || exit 1

# Start application using Python startup script
# Python script directly reads PORT environment variable and starts gunicorn
# This avoids all bash variable expansion complexities
CMD ["python", "/app/start.py"]
