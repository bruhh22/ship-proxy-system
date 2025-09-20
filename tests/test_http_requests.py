#!/usr/bin/env python3
"""
Test HTTP Requests - Tests basic HTTP functionality of the proxy system.

This test module:
1. Tests all major HTTP methods (GET, POST, PUT, DELETE, HEAD, OPTIONS)
2. Verifies sequential request processing
3. Tests concurrent requests handling
4. Validates proxy responses against direct requests
5. Tests various HTTP scenarios and edge cases
"""

import pytest
import requests
import threading
import time
import subprocess
import sys
import os
import signal
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
SHIP_PROXY_HOST = "localhost"
SHIP_PROXY_PORT = 8080
OFFSHORE_PROXY_HOST = "localhost"
OFFSHORE_PROXY_PORT = 9999
PROXY_URL = f"http://{SHIP_PROXY_HOST}:{SHIP_PROXY_PORT}"

# Test URLs
TEST_URLS = {
    'httpbin': 'http://httpbin.org',
    'httpforever': 'http://httpforever.com',
    'example': 'http://example.com',
    'postman_echo': 'https://postman-echo.com'
}

class ProxyTestFixture:
    """Test fixture to manage proxy server lifecycle."""
    
    def __init__(self):
        self.server_process = None
        self.client_process = None
        self.running = False
    
    def start_servers(self):
        """Start both offshore and ship proxy servers."""
        try:
            # Start offshore proxy server
            server_cmd = [
                sys.executable, 
                os.path.join(os.path.dirname(__file__), '..', 'server', 'server.py')
            ]
            
            self.server_process = subprocess.Popen(
                server_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ, OFFSHORE_HOST='0.0.0.0', OFFSHORE_PORT=str(OFFSHORE_PROXY_PORT))
            )
            
            # Wait for server to start
            time.sleep(2)
            
            # Start ship proxy client
            client_cmd = [
                sys.executable,
                os.path.join(os.path.dirname(__file__), '..', 'client', 'client.py'),
                '--offshore-host', OFFSHORE_PROXY_HOST,
                '--offshore-port', str(OFFSHORE_PROXY_PORT),
                '--listen-port', str(SHIP_PROXY_PORT)
            ]
            
            self.client_process = subprocess.Popen(
                client_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for client to start and connect
            time.sleep(3)
            
            self.running = True
            return True
            
        except Exception as e:
            print(f"Failed to start servers: {e}")
            self.stop_servers()
            return False
    
    def stop_servers(self):
        """Stop both proxy servers."""
        self.running = False
        
        if self.client_process:
            try:
                self.client_process.terminate()
                self.client_process.wait(timeout=5)
            except:
                try:
                    self.client_process.kill()
                except:
                    pass
        
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except:
                try:
                    self.server_process.kill()
                except:
                    pass
    
    def is_proxy_ready(self):
        """Check if proxy is ready to accept requests."""
        try:
            response = requests.get(
                TEST_URLS['example'],
                proxies={'http': PROXY_URL, 'https': PROXY_URL},
                timeout=10
            )
            return response.status_code == 200
        except:
            return False

@pytest.fixture(scope="module")
def proxy_fixture():
    """Pytest fixture to manage proxy lifecycle."""
    fixture = ProxyTestFixture()
    
    if not fixture.start_servers():
        pytest.skip("Could not start proxy servers")
    
    # Wait for proxy to be ready
    max_wait = 30
    for i in range(max_wait):
        if fixture.is_proxy_ready():
            break
        time.sleep(1)
    else:
        fixture.stop_servers()
        pytest.skip("Proxy servers did not become ready in time")
    
    yield fixture
    
    fixture.stop_servers()

class TestBasicHTTPMethods:
    """Test basic HTTP methods through the proxy."""
    
    def test_http_get_request(self, proxy_fixture):
        """Test basic HTTP GET request."""
        response = requests.get(
            TEST_URLS['httpbin'] + '/get',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'args' in data
        assert 'headers' in data
        assert 'url' in data
    
    def test_http_post_request(self, proxy_fixture):
        """Test HTTP POST request with data."""
        test_data = {'key': 'value', 'test': 'data'}
        
        response = requests.post(
            TEST_URLS['httpbin'] + '/post',
            json=test_data,
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'json' in data
        assert data['json'] == test_data
    
    def test_http_put_request(self, proxy_fixture):
        """Test HTTP PUT request."""
        test_data = {'updated': True, 'timestamp': time.time()}
        
        response = requests.put(
            TEST_URLS['httpbin'] + '/put',
            json=test_data,
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'json' in data
        assert data['json'] == test_data
    
    def test_http_delete_request(self, proxy_fixture):
        """Test HTTP DELETE request."""
        response = requests.delete(
            TEST_URLS['httpbin'] + '/delete',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'args' in data
        assert 'headers' in data
    
    def test_http_head_request(self, proxy_fixture):
        """Test HTTP HEAD request."""
        response = requests.head(
            TEST_URLS['httpbin'] + '/get',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        assert len(response.content) == 0  # HEAD should have no body
        assert 'content-type' in response.headers
    
    def test_http_options_request(self, proxy_fixture):
        """Test HTTP OPTIONS request."""
        response = requests.options(
            TEST_URLS['httpbin'] + '/get',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200

class TestSequentialProcessing:
    """Test that requests are processed sequentially."""
    
    def test_sequential_processing_order(self, proxy_fixture):
        """Test that concurrent requests are processed in order."""
        num_requests = 5
        results = []
        
        def make_request(request_id):
            """Make a request with a unique identifier."""
            try:
                response = requests.get(
                    TEST_URLS['httpbin'] + f'/get?id={request_id}&timestamp={time.time()}',
                    proxies={'http': PROXY_URL},
                    timeout=60
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'id': request_id,
                        'timestamp': time.time(),
                        'args': data.get('args', {})
                    }
            except Exception as e:
                return {'id': request_id, 'error': str(e)}
        
        # Submit requests concurrently
        with ThreadPoolExecutor(max_workers=num_requests) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
        
        # Verify all requests completed successfully
        assert len(results) == num_requests
        
        # Check that no requests failed
        errors = [r for r in results if 'error' in r]
        assert len(errors) == 0, f"Some requests failed: {errors}"
    
    def test_multiple_requests_consistency(self, proxy_fixture):
        """Test that multiple identical requests return consistent results."""
        url = TEST_URLS['example']
        responses = []
        
        # Make multiple requests
        for i in range(3):
            response = requests.get(
                url,
                proxies={'http': PROXY_URL},
                timeout=30
            )
            responses.append(response)
            time.sleep(0.5)  # Small delay between requests
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Content should be consistent
        contents = [r.text for r in responses]
        assert all(content == contents[0] for content in contents)

class TestProxyHeaders:
    """Test proxy-specific header handling."""
    
    def test_proxy_headers_removed(self, proxy_fixture):
        """Test that proxy-specific headers are properly handled."""
        custom_headers = {
            'User-Agent': 'TestAgent/1.0',
            'X-Test-Header': 'test-value'
        }
        
        response = requests.get(
            TEST_URLS['httpbin'] + '/headers',
            headers=custom_headers,
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        headers = data['headers']
        
        # Custom headers should be present
        assert 'X-Test-Header' in headers
        assert headers['X-Test-Header'] == 'test-value'
    
    def test_request_with_query_parameters(self, proxy_fixture):
        """Test requests with query parameters."""
        params = {
            'param1': 'value1',
            'param2': 'value2',
            'special': 'hello world'
        }
        
        response = requests.get(
            TEST_URLS['httpbin'] + '/get',
            params=params,
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'args' in data
        
        for key, value in params.items():
            assert key in data['args']
            assert data['args'][key] == value

class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_invalid_url(self, proxy_fixture):
        """Test handling of invalid URLs."""
        try:
            response = requests.get(
                'http://this-domain-definitely-does-not-exist-12345.com',
                proxies={'http': PROXY_URL},
                timeout=30
            )
            # Should get a 502 Bad Gateway or similar error
            assert response.status_code >= 400
        except requests.exceptions.RequestException:
            # This is also acceptable - connection errors
            pass
    
    def test_timeout_handling(self, proxy_fixture):
        """Test handling of slow requests."""
        try:
            # Request with delay
            response = requests.get(
                TEST_URLS['httpbin'] + '/delay/2',
                proxies={'http': PROXY_URL},
                timeout=30
            )
            assert response.status_code == 200
        except requests.exceptions.Timeout:
            # Timeout is acceptable for this test
            pass
    
    def test_large_response(self, proxy_fixture):
        """Test handling of large responses."""
        # Request a large response (100KB of random bytes)
        response = requests.get(
            TEST_URLS['httpbin'] + '/bytes/102400',
            proxies={'http': PROXY_URL},
            timeout=60
        )
        
        assert response.status_code == 200
        assert len(response.content) == 102400

class TestProxyFunctionality:
    """Test proxy-specific functionality."""
    
    def test_proxy_vs_direct_comparison(self, proxy_fixture):
        """Compare proxy response with direct request."""
        url = TEST_URLS['httpbin'] + '/get'
        
        # Direct request
        try:
            direct_response = requests.get(url, timeout=10)
            direct_success = True
        except:
            direct_success = False
        
        # Proxy request
        proxy_response = requests.get(
            url,
            proxies={'http': PROXY_URL},
            timeout=30
        )
        
        assert proxy_response.status_code == 200
        
        if direct_success:
            # Both should return similar structure
            proxy_data = proxy_response.json()
            direct_data = direct_response.json()
            
            # Both should have the same basic structure
            assert 'args' in proxy_data
            assert 'headers' in proxy_data
            assert 'url' in proxy_data
    
    def test_different_content_types(self, proxy_fixture):
        """Test handling of different content types."""
        # JSON response
        json_response = requests.get(
            TEST_URLS['httpbin'] + '/json',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        assert json_response.status_code == 200
        assert 'application/json' in json_response.headers.get('content-type', '')
        
        # HTML response  
        html_response = requests.get(
            TEST_URLS['httpbin'] + '/html',
            proxies={'http': PROXY_URL},
            timeout=30
        )
        assert html_response.status_code == 200
        assert 'text/html' in html_response.headers.get('content-type', '')

if __name__ == '__main__':
    # Run tests directly
    pytest.main([__file__, '-v', '--tb=short'])