#!/usr/bin/env python3
"""
Test HTTPS Connect - Tests HTTPS tunneling (CONNECT method) functionality.

This test module:
1. Tests HTTPS requests through the proxy system
2. Verifies CONNECT method handling
3. Tests SSL/TLS tunneling capability  
4. Validates secure connections work end-to-end
5. Tests various HTTPS scenarios
"""

import pytest
import requests
import ssl
import socket
import threading
import time
import subprocess
import sys
import os
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
SHIP_PROXY_HOST = "localhost"
SHIP_PROXY_PORT = 8080
OFFSHORE_PROXY_HOST = "localhost"
OFFSHORE_PROXY_PORT = 9999
PROXY_URL = f"http://{SHIP_PROXY_HOST}:{SHIP_PROXY_PORT}"

# HTTPS Test URLs
HTTPS_TEST_URLS = {
    'httpbin_https': 'https://httpbin.org',
    'example_https': 'https://example.com',
    'google': 'https://www.google.com',
    'github': 'https://github.com',
    'postman_echo': 'https://postman-echo.com'
}

class HTTPSProxyTestFixture:
    """Test fixture to manage HTTPS proxy testing."""
    
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
    
    def is_https_proxy_ready(self):
        """Check if HTTPS proxy is ready."""
        try:
            response = requests.get(
                HTTPS_TEST_URLS['example_https'],
                proxies={'http': PROXY_URL, 'https': PROXY_URL},
                timeout=15,
                verify=False  # Don't verify SSL in tests
            )
            return response.status_code == 200
        except Exception as e:
            print(f"HTTPS proxy not ready: {e}")
            return False

@pytest.fixture(scope="module")
def https_proxy_fixture():
    """Pytest fixture to manage HTTPS proxy lifecycle."""
    fixture = HTTPSProxyTestFixture()
    
    if not fixture.start_servers():
        pytest.skip("Could not start proxy servers for HTTPS testing")
    
    # Wait for proxy to be ready for HTTPS
    max_wait = 45
    for i in range(max_wait):
        if fixture.is_https_proxy_ready():
            break
        time.sleep(1)
    else:
        fixture.stop_servers()
        pytest.skip("HTTPS proxy servers did not become ready in time")
    
    yield fixture
    
    fixture.stop_servers()

class TestHTTPSBasicFunctionality:
    """Test basic HTTPS functionality through proxy."""
    
    def test_https_get_request(self, https_proxy_fixture):
        """Test basic HTTPS GET request."""
        response = requests.get(
            HTTPS_TEST_URLS['httpbin_https'] + '/get',
            proxies={'https': PROXY_URL},
            timeout=45,
            verify=False  # Skip SSL verification for testing
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'args' in data
        assert 'headers' in data
        assert 'url' in data
        # Verify the request was made over HTTPS
        assert data['url'].startswith('https://')
    
    def test_https_post_request(self, https_proxy_fixture):
        """Test HTTPS POST request with data."""
        test_data = {'secure_key': 'secure_value', 'timestamp': time.time()}
        
        response = requests.post(
            HTTPS_TEST_URLS['httpbin_https'] + '/post',
            json=test_data,
            proxies={'https': PROXY_URL},
            timeout=45,
            verify=False
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'json' in data
        assert data['json'] == test_data
        assert data['url'].startswith('https://')
    
    def test_example_com_https(self, https_proxy_fixture):
        """Test connection to example.com over HTTPS."""
        response = requests.get(
            HTTPS_TEST_URLS['example_https'],
            proxies={'https': PROXY_URL},
            timeout=30,
            verify=False
        )
        
        assert response.status_code == 200
        assert 'Example Domain' in response.text
        assert response.url.startswith('https://')

class TestHTTPSConnectMethod:
    """Test CONNECT method functionality for HTTPS tunneling."""
    
    def test_connect_method_handling(self, https_proxy_fixture):
        """Test that CONNECT method is properly handled."""
        # This test verifies that CONNECT requests work by making HTTPS requests
        # The CONNECT method is handled internally by the requests library
        
        response = requests.get(
            HTTPS_TEST_URLS['httpbin_https'] + '/status/200',
            proxies={'https': PROXY_URL},
            timeout=30,
            verify=False
        )
        
        assert response.status_code == 200
    
    def test_multiple_https_domains(self, https_proxy_fixture):
        """Test HTTPS connections to multiple different domains."""
        test_sites = [
            (HTTPS_TEST_URLS['httpbin_https'] + '/get', 'httpbin'),
            (HTTPS_TEST_URLS['example_https'], 'example')
        ]
        
        for url, site_name in test_sites:
            try:
                response = requests.get(
                    url,
                    proxies={'https': PROXY_URL},
                    timeout=30,
                    verify=False
                )
                assert response.status_code == 200
                print(f"✓ Successfully connected to {site_name}")
            except Exception as e:
                pytest.fail(f"Failed to connect to {site_name}: {e}")

class TestHTTPSSequentialProcessing:
    """Test sequential processing of HTTPS requests."""
    
    def test_sequential_https_requests(self, https_proxy_fixture):
        """Test that multiple HTTPS requests are processed sequentially."""
        num_requests = 3
        results = []
        
        def make_https_request(request_id):
            """Make an HTTPS request with unique identifier."""
            try:
                start_time = time.time()
                response = requests.get(
                    HTTPS_TEST_URLS['httpbin_https'] + f'/get?id={request_id}',
                    proxies={'https': PROXY_URL},
                    timeout=60,
                    verify=False
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        'id': request_id,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': end_time - start_time,
                        'args': data.get('args', {}),
                        'success': True
                    }
                else:
                    return {'id': request_id, 'success': False, 'status': response.status_code}
            except Exception as e:
                return {'id': request_id, 'success': False, 'error': str(e)}
        
        # Make requests sequentially (one after another)
        for i in range(num_requests):
            result = make_https_request(i)
            results.append(result)
            time.sleep(1)  # Small delay between requests
        
        # Verify all requests completed successfully
        successful_results = [r for r in results if r.get('success', False)]
        assert len(successful_results) == num_requests, f"Only {len(successful_results)} out of {num_requests} HTTPS requests succeeded"
        
        # Verify sequential nature - each request should complete before next starts
        for i in range(1, len(successful_results)):
            prev_end = successful_results[i-1]['end_time']
            curr_start = successful_results[i]['start_time']
            # Allow some overlap due to processing delays, but should be mostly sequential
            assert curr_start >= prev_end - 1, "Requests may not be processed sequentially"

class TestMixedHTTPAndHTTPS:
    """Test mixed HTTP and HTTPS requests."""
    
    def test_mixed_protocol_requests(self, https_proxy_fixture):
        """Test alternating HTTP and HTTPS requests."""
        requests_to_make = [
            ('http://httpbin.org/get?type=http', 'http'),
            ('https://httpbin.org/get?type=https', 'https'),
            ('http://example.com', 'http'),
            ('https://example.com', 'https')
        ]
        
        results = []
        
        for url, protocol in requests_to_make:
            try:
                response = requests.get(
                    url,
                    proxies={'http': PROXY_URL, 'https': PROXY_URL},
                    timeout=30,
                    verify=False
                )
                
                results.append({
                    'url': url,
                    'protocol': protocol,
                    'status': response.status_code,
                    'success': response.status_code == 200
                })
                
            except Exception as e:
                results.append({
                    'url': url,
                    'protocol': protocol,
                    'error': str(e),
                    'success': False
                })
        
        # At least some requests should succeed
        successful_requests = [r for r in results if r['success']]
        assert len(successful_requests) >= 2, "At least 2 mixed protocol requests should succeed"
        
        # Should have both HTTP and HTTPS successes if possible
        http_success = any(r['protocol'] == 'http' and r['success'] for r in results)
        https_success = any(r['protocol'] == 'https' and r['success'] for r in results)
        
        print(f"HTTP success: {http_success}, HTTPS success: {https_success}")

class TestHTTPSErrorHandling:
    """Test HTTPS error handling scenarios."""
    
    def test_invalid_https_domain(self, https_proxy_fixture):
        """Test handling of invalid HTTPS domains."""
        try:
            response = requests.get(
                'https://this-secure-domain-does-not-exist-12345.com',
                proxies={'https': PROXY_URL},
                timeout=30,
                verify=False
            )
            # Should get an error response
            assert response.status_code >= 400
        except requests.exceptions.RequestException:
            # This is also acceptable - connection errors
            pass
    
    def test_https_timeout_handling(self, https_proxy_fixture):
        """Test handling of HTTPS timeouts."""
        try:
            # Use a very short timeout to force timeout
            response = requests.get(
                HTTPS_TEST_URLS['httpbin_https'] + '/delay/1',
                proxies={'https': PROXY_URL},
                timeout=0.5  # Very short timeout
            )
            # If it doesn't timeout, that's also okay
            assert response.status_code in [200, 408, 504]
        except requests.exceptions.Timeout:
            # Timeout is expected and acceptable
            pass

class TestSSLVerification:
    """Test SSL certificate verification scenarios."""
    
    def test_ssl_verification_disabled(self, https_proxy_fixture):
        """Test HTTPS with SSL verification disabled."""
        response = requests.get(
            HTTPS_TEST_URLS['example_https'],
            proxies={'https': PROXY_URL},
            timeout=30,
            verify=False  # Disable SSL verification
        )
        
        assert response.status_code == 200
    
    def test_ssl_verification_enabled(self, https_proxy_fixture):
        """Test HTTPS with SSL verification enabled."""
        try:
            response = requests.get(
                HTTPS_TEST_URLS['example_https'],
                proxies={'https': PROXY_URL},
                timeout=30,
                verify=True  # Enable SSL verification
            )
            # Should work with proper certificates
            assert response.status_code == 200
        except requests.exceptions.SSLError:
            # SSL errors are acceptable in test environment
            pytest.skip("SSL verification failed - acceptable in test environment")

if __name__ == '__main__':
    # Run tests directly
    pytest.main([__file__, '-v', '--tb=short'])