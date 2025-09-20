# server/__init__.py
"""
Offshore Proxy Server Package

This package contains the offshore proxy server implementation that:
- Receives HTTP/HTTPS requests from the ship proxy over TCP
- Forwards requests to target internet servers  
- Returns responses back through the same persistent TCP connection
- Handles sequential request processing to maintain single TCP connection

Main Components:
- server.py: Main offshore proxy server implementation
- Dockerfile: Container configuration for deployment
- requirements.txt: Python dependencies
"""

from .server import OffshoreProxyServer

__version__ = "1.0.0"
__author__ = "Ship Proxy System Team"
__description__ = "Offshore proxy server for the cruise ship internet cost optimization system"

# Export main class for external use
__all__ = ['OffshoreProxyServer']