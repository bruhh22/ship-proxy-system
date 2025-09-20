#!/usr/bin/env python3
"""
Ship Proxy Client - Acts as HTTP proxy server on the ship.

This client:
1. Listens on port 8080 for HTTP proxy requests from browsers/curl
2. Queues incoming requests for sequential processing
3. Maintains single persistent TCP connection to offshore proxy
4. Forwards requests using custom framing protocol
5. Returns responses back to original clients
6. Supports all HTTP methods including HTTPS CONNECT tunneling
"""

import socket
import threading
import logging
import sys
import os
import queue
import time
import argparse
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
import io

# Add utils to path for importing protocol
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.protocol import send_message, read_message, create_tcp_connection, close_connection, MSG_REQUEST, MSG_RESPONSE
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
    
    def create_tcp_connection(host, port, timeout=30):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            return sock
        except:
            return None
    
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

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP Server with threading support for concurrent request handling."""
    daemon_threads = True
    allow_reuse_address = True

class ShipProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ship proxy - handles all HTTP methods."""
    
    # Supported HTTP methods
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def do_HEAD(self):
        self.handle_request()
    
    def do_OPTIONS(self):
        self.handle_request()
    
    def do_PATCH(self):
        self.handle_request()
    
    def do_CONNECT(self):
        self.handle_request()
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def handle_request(self):
        """Handle any HTTP request by queuing it for sequential processing."""
        request_id = f"{self.address_string()}-{int(time.time() * 1000)}"
        
        try:
            # Build the complete HTTP request data
            request_data = self.build_request_data()
            if not request_data:
                self.send_error(400, "Bad Request - Could not parse request")
                return
            
            logger.info(f"[{request_id}] Received {self.command} {self.path}")
            
            # Create synchronization objects for response
            response_event = threading.Event()
            response_container = {'data': None, 'error': None}
            
            # Create request item for queue
            request_item = {
                'id': request_id,
                'request_data': request_data,
                'response_event': response_event,
                'response_container': response_container,
                'method': self.command,
                'path': self.path
            }
            
            # Add to processing queue
            self.server.request_queue.put(request_item)
            logger.debug(f"[{request_id}] Queued for processing")
            
            # Wait for response with timeout
            if response_event.wait(timeout=60):  # 60 second timeout
                if response_container['error']:
                    logger.error(f"[{request_id}] Error: {response_container['error']}")
                    self.send_error(502, f"Bad Gateway: {response_container['error']}")
                elif response_container['data']:
                    logger.info(f"[{request_id}] Sending response ({len(response_container['data'])} bytes)")
                    self.send_raw_response(response_container['data'])
                else:
                    logger.error(f"[{request_id}] No response data received")
                    self.send_error(502, "Bad Gateway - No response from offshore proxy")
            else:
                logger.error(f"[{request_id}] Timeout waiting for response")
                self.send_error(504, "Gateway Timeout")
                
        except Exception as e:
            logger.error(f"[{request_id}] Error handling request: {e}")
            try:
                self.send_error(500, f"Internal Server Error: {str(e)}")
            except:
                pass  # Connection might be closed
    
    def build_request_data(self):
        """Build complete HTTP request data including headers and body."""
        try:
            # Start with request line
            request_line = f"{self.command} {self.path} {self.request_version}\r\n"
            
            # Add all headers
            headers_str = ""
            for header_name, header_value in self.headers.items():
                headers_str += f"{header_name}: {header_value}\r\n"
            
            # Add empty line to separate headers from body
            headers_str += "\r\n"
            
            # Read body if present
            body = b""
            content_length = self.headers.get('Content-Length')
            if content_length:
                try:
                    content_length = int(content_length)
                    if content_length > 0:
                        body = self.rfile.read(content_length)
                except (ValueError, OSError) as e:
                    logger.warning(f"Error reading request body: {e}")
            
            # Combine request line, headers, and body
            request_bytes = (request_line + headers_str).encode('utf-8') + body
            return request_bytes
            
        except Exception as e:
            logger.error(f"Error building request data: {e}")
            return None
    
    def send_raw_response(self, response_data):
        """Send raw HTTP response data back to client."""
        try:
            self.wfile.write(response_data)
            self.wfile.flush()
        except Exception as e:
            logger.error(f"Error sending response: {e}")

class ShipProxyClient:
    """
    Ship Proxy Client - manages HTTP proxy server and offshore connection.
    """
    
    def __init__(self, offshore_host='localhost', offshore_port=9999, listen_port=8080):
        self.offshore_host = offshore_host
        self.offshore_port = offshore_port
        self.listen_port = listen_port
        self.request_queue = queue.Queue()
        self.offshore_socket = None
        self.running = False
        self.processor_thread = None
        self.connection_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    def start(self):
        """Start the ship proxy client."""
        logger.info("=" * 60)
        logger.info("SHIP PROXY CLIENT STARTING")
        logger.info("=" * 60)
        logger.info(f"Listen Port: {self.listen_port}")
        logger.info(f"Offshore Proxy: {self.offshore_host}:{self.offshore_port}")
        
        # Connect to offshore proxy
        if not self.connect_to_offshore():
            logger.error("Failed to connect to offshore proxy. Exiting.")
            return False
        
        self.running = True
        
        # Start request processor thread
        self.processor_thread = threading.Thread(
            target=self.process_requests, 
            daemon=True,
            name="RequestProcessor"
        )
        self.processor_thread.start()
        logger.info("Request processor thread started")
        
        # Start HTTP proxy server
        try:
            httpd = ThreadingHTTPServer(('0.0.0.0', self.listen_port), ShipProxyHandler)
            httpd.request_queue = self.request_queue
            
            logger.info(f"Ship Proxy listening on port {self.listen_port}")
            logger.info(f"Configure your browser/curl to use: http://localhost:{self.listen_port}")
            logger.info("=" * 60)
            
            httpd.serve_forever()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"HTTP server error: {e}")
        finally:
            self.stop()
        
        return True
    
    def connect_to_offshore(self):
        """Establish connection to offshore proxy with retry logic."""
        for attempt in range(self.max_reconnect_attempts):
            try:
                logger.info(f"Connecting to offshore proxy {self.offshore_host}:{self.offshore_port} (attempt {attempt + 1})")
                self.offshore_socket = create_tcp_connection(
                    self.offshore_host, 
                    self.offshore_port, 
                    timeout=10
                )
                
                if self.offshore_socket:
                    logger.info("Successfully connected to offshore proxy")
                    self.reconnect_attempts = 0
                    return True
                else:
                    logger.warning(f"Failed to connect (attempt {attempt + 1})")
                    
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
            
            if attempt < self.max_reconnect_attempts - 1:
                wait_time = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        logger.error("All connection attempts failed")
        return False
    
    def process_requests(self):
        """Process queued requests sequentially over the single TCP connection."""
        logger.info("Request processor started - handling requests sequentially")
        
        while self.running:
            try:
                # Get next request from queue (with timeout to allow checking self.running)
                try:
                    request_item = self.request_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                request_id = request_item['id']
                request_data = request_item['request_data']
                response_event = request_item['response_event']
                response_container = request_item['response_container']
                method = request_item['method']
                path = request_item['path']
                
                logger.debug(f"[{request_id}] Processing {method} {path}")
                
                try:
                    # Ensure we have a valid connection
                    with self.connection_lock:
                        if not self.offshore_socket:
                            if not self.connect_to_offshore():
                                response_container['error'] = "Cannot connect to offshore proxy"
                                response_event.set()
                                self.request_queue.task_done()
                                continue
                        
                        # Send request to offshore proxy
                        if not send_message(self.offshore_socket, MSG_REQUEST, request_data):
                            logger.error(f"[{request_id}] Failed to send request")
                            # Try to reconnect
                            close_connection(self.offshore_socket)
                            self.offshore_socket = None
                            if self.connect_to_offshore():
                                # Retry sending
                                if not send_message(self.offshore_socket, MSG_REQUEST, request_data):
                                    response_container['error'] = "Failed to send request after reconnection"
                                    response_event.set()
                                    self.request_queue.task_done()
                                    continue
                            else:
                                response_container['error'] = "Lost connection to offshore proxy"
                                response_event.set()
                                self.request_queue.task_done()
                                continue
                        
                        # Wait for response from offshore proxy
                        msg_type, payload = read_message(self.offshore_socket)
                        
                        if msg_type == MSG_RESPONSE and payload is not None:
                            response_container['data'] = payload
                            logger.debug(f"[{request_id}] Received response ({len(payload)} bytes)")
                        else:
                            logger.error(f"[{request_id}] Invalid response from offshore proxy")
                            response_container['error'] = "Invalid response from offshore proxy"
                            # Connection might be broken
                            close_connection(self.offshore_socket)
                            self.offshore_socket = None
                
                except Exception as e:
                    logger.error(f"[{request_id}] Error processing request: {e}")
                    response_container['error'] = str(e)
                    # Close connection on error
                    with self.connection_lock:
                        if self.offshore_socket:
                            close_connection(self.offshore_socket)
                            self.offshore_socket = None
                
                # Signal completion
                response_event.set()
                self.request_queue.task_done()
                
            except Exception as e:
                logger.error(f"Processor thread error: {e}")
                if self.running:
                    time.sleep(1)  # Brief pause before retrying
        
        logger.info("Request processor stopped")
    
    def stop(self):
        """Stop the ship proxy client."""
        logger.info("Stopping Ship Proxy Client...")
        self.running = False
        
        # Close offshore connection
        with self.connection_lock:
            if self.offshore_socket:
                close_connection(self.offshore_socket)
                self.offshore_socket = None
        
        # Wait for processor thread to finish
        if self.processor_thread and self.processor_thread.is_alive():
            logger.info("Waiting for request processor to stop...")
            self.processor_thread.join(timeout=5)
        
        logger.info("Ship Proxy Client stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    global client_instance
    if client_instance:
        client_instance.stop()
    sys.exit(0)

# Global client instance for signal handling
client_instance = None

def main():
    """Main function with command line argument parsing."""
    global client_instance
    
    parser = argparse.ArgumentParser(
        description='Ship Proxy Client - HTTP proxy server for cruise ship internet optimization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --offshore-host=proxy.example.com --offshore-port=9999
  %(prog)s --listen-port=8080 --offshore-host=localhost
  
Test with curl:
  curl -x http://localhost:8080 http://httpforever.com/
  curl -x http://localhost:8080 -X POST -d "test=data" http://httpbin.org/post
        """
    )
    
    parser.add_argument(
        '--offshore-host', 
        default=os.getenv('OFFSHORE_HOST', 'localhost'),
        help='Offshore proxy hostname/IP (default: localhost, env: OFFSHORE_HOST)'
    )
    
    parser.add_argument(
        '--offshore-port', 
        type=int, 
        default=int(os.getenv('OFFSHORE_PORT', '9999')),
        help='Offshore proxy port (default: 9999, env: OFFSHORE_PORT)'
    )
    
    parser.add_argument(
        '--listen-port', 
        type=int, 
        default=int(os.getenv('LISTEN_PORT', '8080')),
        help='Port to listen on for proxy requests (default: 8080, env: LISTEN_PORT)'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=os.getenv('LOG_LEVEL', 'INFO'),
        help='Set logging level (default: INFO, env: LOG_LEVEL)'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start client
    client_instance = ShipProxyClient(
        offshore_host=args.offshore_host,
        offshore_port=args.offshore_port,
        listen_port=args.listen_port
    )
    
    try:
        success = client_instance.start()
        if not success:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)
    finally:
        if client_instance:
            client_instance.stop()

if __name__ == "__main__":
    main()