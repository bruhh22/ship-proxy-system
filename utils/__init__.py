# utils/__init__.py
"""
Utils package for the ship proxy system.

This package provides shared utilities for communication between
the ship proxy (client) and offshore proxy (server).
"""

# Import main protocol functions and constants for easy access
from .protocol import (
    send_message,
    read_message,
    create_tcp_connection,
    close_connection,
    format_http_message,
    is_valid_message_type,
    MSG_REQUEST,
    MSG_RESPONSE
)

# Package metadata
__version__ = "1.0.0"
__author__ = "Ship Proxy System"
__description__ = "Shared utilities for the cruise ship proxy system"

# Make commonly used functions available at package level
__all__ = [
    'send_message',
    'read_message', 
    'create_tcp_connection',
    'close_connection',
    'format_http_message',
    'is_valid_message_type',
    'MSG_REQUEST',
    'MSG_RESPONSE'
]