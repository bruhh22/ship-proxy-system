# Offshore Proxy Server Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY server/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy utils directory (shared protocol code)
COPY utils/ ./utils/

# Copy server code
COPY server/server.py .

# Create non-root user for security
RUN groupadd -r proxyuser && useradd -r -g proxyuser proxyuser
RUN chown -R proxyuser:proxyuser /app
USER proxyuser

# Expose the port the server runs on
EXPOSE 9999

# Health check to ensure the server is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.settimeout(5); s.connect(('localhost', 9999)); s.close()" || exit 1

# Set environment variables
ENV OFFSHORE_HOST=0.0.0.0
ENV OFFSHORE_PORT=9999
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Add metadata
LABEL maintainer="Ship Proxy System"
LABEL description="Offshore Proxy Server for the Ship Proxy System"
LABEL version="1.0.0"

# Run the server
CMD ["python", "server.py"]