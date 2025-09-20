# Ship Proxy Client Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY client/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy utils directory (shared protocol code)
COPY utils/ ./utils/

# Copy client code
COPY client/client.py .

# Create non-root user for security
RUN groupadd -r proxyuser && useradd -r -g proxyuser proxyuser
RUN chown -R proxyuser:proxyuser /app
USER proxyuser

# Expose the port the client runs on
EXPOSE 8080

# Health check to ensure the client is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.settimeout(5); s.connect(('localhost', 8080)); s.close()" || exit 1

# Set environment variables with defaults
ENV OFFSHORE_HOST=offshore-proxy
ENV OFFSHORE_PORT=9999
ENV LISTEN_PORT=8080
ENV LOG_LEVEL=INFO
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Add metadata
LABEL maintainer="Ship Proxy System"
LABEL description="Ship Proxy Client for the cruise ship internet cost optimization system"
LABEL version="1.0.0"

# Run the client with environment variable configuration
CMD ["python", "client.py"]