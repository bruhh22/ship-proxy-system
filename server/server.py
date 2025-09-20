#!/usr/bin/env python3
"""
Offshore Proxy Server - Receives HTTP requests from ship proxy,
forwards them to target servers, and sends responses back.

This server:
1. Listens on port 9999 for connections from Ship Proxy
2. Accepts one persistent TCP connection
3. Reads framed HTTP requests using custom protocol
4. Forwards requests to target internet servers
5. Sends responses back through the same TCP connection
6. Handles both HTTP and HTTPS (CONNECT method) requests
"""

import socket
import threading
import logging
import sys
import os
import http.client
import ssl
import urllib.parse
from urllib.parse import urlparse
import time
import signal

# Add utils to path for importing protocol
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.protocol import send_message, read_message, MSG_REQUEST, MSG_RESPONSE, close_connection
except ImportError:
    # Fallback if utils not available - basic implementation
    import struct
    
    MSG_REQUEST = 0
    MSG_RESPONSE = 1
    
    def send_message(sock, msg_type, payload):
        try:
            payload_length = len(payload)
            header = struct.pack('>I', payload_length) + struct.pack('B', msg_type)
            sock.sendall(header + payload)
            return True
        except:
            return False
    
    def read_message(sock):
        try:
            header = sock.recv(5)
            if len(header) != 5:
                return None, None
            payload_length = struct.unpack('>I', header[:4])[0]
            msg_type = struct.unpack('B', header[4:5])[0]
            
            payload = b''
            while len(payload) < payload_length:
                chunk = sock.recv(payload_length - len(payload))
                if not chunk:
                    return None, None
                payload += chunk
            
            return msg_type, payload
        except:
            return None, None
    
    def close_connection(sock):
        if sock:
            try:
                sock.close()
            except:
                pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OffshoreProxyServer:
    """
    Offshore Proxy Server that handles HTTP/HTTPS requests from Ship Proxy.
    """
    
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.client_connections = []
        
    def start(self):
        """Start the offshore proxy server."""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)  # Allow multiple connections (though we expect only one)
            self.running = True
            
            logger.info(f"Offshore Proxy Server listening on {self.host}:{self.port}")
            logger.info("Waiting for Ship Proxy connection...")
            
            # Accept connections in a loop
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    logger.info(f"Ship proxy connected from {address}")
                    
                    # Handle each connection in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_ship_connection,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    self.client_connections.append((client_socket, client_thread))
                    
                except socket.error as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                    break
                except Exception as e:
                    if self.running:
                        logger.error(f"Unexpected error in server loop: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Server startup error: {e}")
        finally:
            self.stop()
    
    def handle_ship_connection(self, ship_socket, address):
        """Handle persistent connection from ship proxy."""
        connection_id = f"{address[0]}:{address[1]}"
        logger.info(f"Handling connection from {connection_id}")
        
        try:
            while self.running:
                # Read request from ship proxy
                msg_type, payload = read_message(ship_socket)
                
                if msg_type is None or payload is None:
                    logger.warning(f"Connection {connection_id} closed or invalid message received")
                    break
                
                if msg_type != MSG_REQUEST:
                    logger.warning(f"Unexpected message type from {connection_id}: {msg_type}")
                    continue
                
                logger.debug(f"Received request from {connection_id}, payload size: {len(payload)}")
                
                # Process the HTTP request
                response = self.process_http_request(payload, connection_id)
                
                # Send response back to ship proxy
                if not send_message(ship_socket, MSG_RESPONSE, response):
                    logger.error(f"Failed to send response to {connection_id}")
                    break
                
                logger.debug(f"Sent response to {connection_id}, response size: {len(response)}")
                    
        except Exception as e:
            logger.error(f"Error handling connection {connection_id}: {e}")
        finally:
            close_connection(ship_socket)
            logger.info(f"Connection {connection_id} closed")
    
    def process_http_request(self, request_data, connection_id):
        """Process HTTP request and return response."""
        try:
            # Parse the HTTP request
            request_str = request_data.decode('utf-8', errors='replace')
            lines = request_str.split('\r\n')
            
            if not lines:
                return self.create_error_response(400, "Bad Request - Empty request")
            
            # Parse request line
            request_line = lines[0].strip()
            if not request_line:
                return self.create_error_response(400, "Bad Request - Empty request line")
            
            parts = request_line.split(' ')
            if len(parts) != 3:
                return self.create_error_response(400, f"Bad Request - Invalid request line: {request_line}")
            
            method, url, version = parts
            logger.info(f"[{connection_id}] Processing {method} {url}")
            
            # Handle CONNECT method for HTTPS tunneling
            if method.upper() == 'CONNECT':
                return self.handle_connect_method(url, connection_id)
            
            # Parse URL and ensure it's absolute
            if not url.startswith('http://') and not url.startswith('https://'):
                # If it's a relative URL in proxy context, it should be absolute
                # For proxy requests, the URL should always be absolute
                if url.startswith('/'):
                    return self.create_error_response(400, "Bad Request - This is a proxy server. Configure your browser to use http://localhost:8080 as HTTP/HTTPS proxy, or use curl -x http://localhost:8080 <URL>")
                # Try to add http:// prefix
                url = 'http://' + url
            
            parsed_url = urlparse(url)
            if not parsed_url.hostname:
                return self.create_error_response(400, f"Bad Request - Invalid URL: {url}")
            
            host = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
            path = parsed_url.path + ('?' + parsed_url.query if parsed_url.query else '')
            
            if not path:
                path = '/'
            
            # Extract headers and body
            headers = {}
            body = b''
            body_start = -1
            
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == '':  # Empty line indicates start of body
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            # Extract body if present
            if body_start > 0:
                body_lines = lines[body_start:]
                if body_lines:
                    body = '\r\n'.join(body_lines).encode('utf-8')
            
            # Remove problematic headers that might cause issues
            headers_to_remove = ['proxy-connection', 'proxy-authorization']
            for header in headers_to_remove:
                headers.pop(header, None)
                headers.pop(header.title(), None)
                headers.pop(header.upper(), None)
                headers.pop(header.lower(), None)
            
            # Make the actual HTTP request
            return self.make_http_request(
                method, host, port, path, headers, body, 
                parsed_url.scheme == 'https', connection_id
            )
            
        except UnicodeDecodeError as e:
            logger.error(f"[{connection_id}] Unicode decode error: {e}")
            return self.create_error_response(400, "Bad Request - Invalid encoding")
        except Exception as e:
            logger.error(f"[{connection_id}] Error processing request: {e}")
            return self.create_error_response(500, f"Internal Server Error: {str(e)}")
    
    def make_http_request(self, method, host, port, path, headers, body, use_ssl, connection_id):
        """Make HTTP request to target server."""
        try:
            logger.debug(f"[{connection_id}] Connecting to {host}:{port} (SSL: {use_ssl})")
            
            # Create connection
            if use_ssl:
                # Create SSL context with relaxed verification for testing
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                connection = http.client.HTTPSConnection(
                    host, port, timeout=30, context=context
                )
            else:
                connection = http.client.HTTPConnection(host, port, timeout=30)
            
            # Connect
            connection.connect()
            
            # Make request
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            
            # Read response body
            response_body = response.read()
            
            logger.info(f"[{connection_id}] {method} {host}:{port}{path} -> {response.status} {response.reason}")
            
            # Create simple, clean HTTP response
            response_lines = [f"HTTP/1.1 {response.status} {response.reason}"]
            
            # Add only essential headers
            response_lines.append(f"Content-Length: {len(response_body)}")
            response_lines.append("Connection: close")
            
            # Add original headers that are safe
            for header, value in response.getheaders():
                header_lower = header.lower()
                if header_lower not in ['connection', 'transfer-encoding', 'content-length']:
                    clean_value = str(value).strip()
                    response_lines.append(f"{header}: {clean_value}")
            
            # Add empty line before body
            response_lines.append('')
            
            # Combine with proper line endings
            response_text = '\r\n'.join(response_lines)
            full_response = response_text.encode('utf-8') + response_body
            
            connection.close()
            return full_response
            
        except socket.timeout:
            logger.error(f"[{connection_id}] Timeout connecting to {host}:{port}")
            return self.create_error_response(504, "Gateway Timeout")
        except socket.gaierror as e:
            logger.error(f"[{connection_id}] DNS resolution failed for {host}: {e}")
            return self.create_error_response(502, f"Bad Gateway - DNS resolution failed: {host}")
        except ConnectionRefusedError:
            logger.error(f"[{connection_id}] Connection refused by {host}:{port}")
            return self.create_error_response(502, f"Bad Gateway - Connection refused: {host}:{port}")
        except ssl.SSLError as e:
            logger.error(f"[{connection_id}] SSL error connecting to {host}:{port}: {e}")
            return self.create_error_response(502, f"Bad Gateway - SSL error: {str(e)}")
        except Exception as e:
            logger.error(f"[{connection_id}] Error making HTTP request to {host}:{port}: {e}")
            return self.create_error_response(502, f"Bad Gateway: {str(e)}")
    
    def handle_connect_method(self, url, connection_id):
        """Handle CONNECT method for HTTPS tunneling."""
        logger.info(f"[{connection_id}] CONNECT request for {url}")
        
        # For CONNECT method, we just return 200 Connection Established
        # In a full implementation, this would establish a tunnel
        response = "HTTP/1.1 200 Connection Established\r\n\r\n"
        return response.encode('utf-8')
    
    def create_error_response(self, status_code, reason):
        """Create HTTP error response."""
        error_body = f"""<!DOCTYPE html>
<html>
<head><title>{status_code} {reason}</title></head>
<body>
<h1>{status_code} {reason}</h1>
<p>The offshore proxy server encountered an error.</p>
<hr>
<p><em>Offshore Proxy Server</em></p>
</body>
</html>"""
        
        response = f"HTTP/1.1 {status_code} {reason}\r\n"
        response += "Content-Type: text/html\r\n"
        response += f"Content-Length: {len(error_body)}\r\n"
        response += "Connection: close\r\n"
        response += f"\r\n{error_body}"
        
        return response.encode('utf-8')
    
    def stop(self):
        """Stop the server and close all connections."""
        logger.info("Stopping Offshore Proxy Server...")
        self.running = False
        
        # Close all client connections
        for client_socket, thread in self.client_connections:
            close_connection(client_socket)
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        logger.info("Offshore Proxy Server stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    global server_instance
    if server_instance:
        server_instance.stop()
    sys.exit(0)

# Global server instance for signal handling
server_instance = None

def main():
    """Main function."""
    global server_instance
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration from environment variables
    host = os.getenv('OFFSHORE_HOST', '0.0.0.0')
    port = int(os.getenv('OFFSHORE_PORT', '9999'))
    
    # Create and start server
    server_instance = OffshoreProxyServer(host, port)
    
    try:
        logger.info("Starting Offshore Proxy Server...")
        server_instance.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        if server_instance:
            server_instance.stop()

if __name__ == "__main__":
    main()