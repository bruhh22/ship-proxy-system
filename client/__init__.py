# client/__init__.py
"""
Ship Proxy Client Package

This package contains the ship proxy client implementation that:
- Acts as HTTP proxy server listening on port 8080
- Accepts proxy requests from browsers and curl clients
- Queues requests for sequential processing over single TCP connection
- Forwards requests to offshore proxy using custom framing protocol
- Returns responses back to original clients
- Supports all HTTP methods including HTTPS CONNECT tunneling

Main Components:
- client.py: Main ship proxy client implementation with HTTP server
- Dockerfile: Container configuration for deployment  
- requirements.txt: Python dependencies (uses stdlib only)

Usage:
    python client.py --offshore-host=proxy.example.com --offshore-port=9999
    
    Configure browser proxy: http://localhost:8080
    Test with curl: curl -x http://localhost:8080 http://example.com/
"""

from .client import ShipProxyClient, ShipProxyHandler

__version__ = "1.0.0"
__author__ = "Ship Proxy System Team" 
__description__ = "Ship proxy client for cruise ship internet cost optimization"

# Export main classes for external use
__all__ = ['ShipProxyClient', 'ShipProxyHandler']