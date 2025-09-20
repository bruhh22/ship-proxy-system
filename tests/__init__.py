# tests/__init__.py
"""
Test Suite for Ship Proxy System

This package contains comprehensive tests for the cruise ship proxy system:

Test Modules:
- test_http_requests.py: Tests basic HTTP functionality (GET, POST, PUT, DELETE, etc.)
- test_https_connect.py: Tests HTTPS tunneling and CONNECT method functionality

Test Coverage:
✓ All HTTP methods (GET, POST, PUT, DELETE, HEAD, OPTIONS, PATCH)
✓ HTTPS requests with CONNECT method tunneling
✓ Sequential request processing verification
✓ Concurrent request handling
✓ Error handling and edge cases
✓ Proxy vs direct request comparison
✓ Different content types and response sizes
✓ Mixed HTTP/HTTPS protocol handling
✓ SSL/TLS verification scenarios

Usage:
    # Run all tests
    pytest tests/
    
    # Run specific test module
    pytest tests/test_http_requests.py -v
    pytest tests/test_https_connect.py -v
    
    # Run with coverage
    pytest tests/ --cov=client --cov=server --cov=utils
    
    # Run specific test class
    pytest tests/test_http_requests.py::TestBasicHTTPMethods -v

Test Requirements:
- pytest >= 7.0.0
- requests >= 2.28.0
- Both client and server components must be functional
- Network access for external test sites (httpbin.org, example.com)

Test Environment:
- Ship Proxy: localhost:8080
- Offshore Proxy: localhost:9999
- Test fixtures automatically start/stop proxy servers
- Tests use real HTTP endpoints for validation
"""

import sys
import os

# Add project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

__version__ = "1.0.0"
__author__ = "Ship Proxy System Team"
__description__ = "Comprehensive test suite for the cruise ship proxy system"

# Test configuration constants
TEST_CONFIG = {
    'SHIP_PROXY_HOST': 'localhost',
    'SHIP_PROXY_PORT': 8080,
    'OFFSHORE_PROXY_HOST': 'localhost', 
    'OFFSHORE_PROXY_PORT': 9999,
    'DEFAULT_TIMEOUT': 30,
    'STARTUP_WAIT_TIME': 5,
    'MAX_STARTUP_WAIT': 30
}

# Test URLs for validation
TEST_ENDPOINTS = {
    'http_test': 'http://httpbin.org',
    'https_test': 'https://httpbin.org',
    'simple_http': 'http://example.com',
    'simple_https': 'https://example.com'
}

__all__ = ['TEST_CONFIG', 'TEST_ENDPOINTS']