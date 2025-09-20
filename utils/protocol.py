# utils/protocol.py
"""
Custom binary protocol for framing HTTP messages over a single TCP connection.

Message Format:
[ 4 bytes length ][ 1 byte type ][ payload (length bytes) ]

- Length: unsigned 32-bit int, big-endian (size of payload only)
- Type: 1 byte (0=request, 1=response)
- Payload: raw HTTP request or response bytes
"""

import socket
import struct
import logging

# Message type constants
MSG_REQUEST = 0
MSG_RESPONSE = 1

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def send_message(sock, msg_type, payload):
    """
    Send a framed message over TCP socket.
    
    Args:
        sock: TCP socket to send over
        msg_type: Message type (MSG_REQUEST or MSG_RESPONSE)
        payload: Raw bytes to send (HTTP request/response)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Calculate payload length
        payload_length = len(payload)
        
        # Pack header: 4 bytes length (big-endian) + 1 byte type
        header = struct.pack('>I', payload_length) + struct.pack('B', msg_type)
        
        # Send header + payload
        sock.sendall(header + payload)
        
        logger.debug(f"Sent message: type={msg_type}, length={payload_length}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


def read_message(sock):
    """
    Read a framed message from TCP socket.
    
    Args:
        sock: TCP socket to read from
    
    Returns:
        tuple: (msg_type, payload) if successful, (None, None) if failed
    """
    try:
        # Read header (5 bytes: 4 bytes length + 1 byte type)
        header = _read_exact(sock, 5)
        if not header:
            return None, None
        
        # Unpack header
        payload_length = struct.unpack('>I', header[:4])[0]
        msg_type = struct.unpack('B', header[4:5])[0]
        
        # Read payload
        payload = _read_exact(sock, payload_length)
        if payload is None:
            return None, None
        
        logger.debug(f"Received message: type={msg_type}, length={payload_length}")
        return msg_type, payload
        
    except Exception as e:
        logger.error(f"Error reading message: {e}")
        return None, None


def _read_exact(sock, num_bytes):
    """
    Read exactly num_bytes from socket.
    
    Args:
        sock: TCP socket to read from
        num_bytes: Exact number of bytes to read
    
    Returns:
        bytes: Data read, or None if connection closed/error
    """
    data = b''
    while len(data) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(data))
            if not chunk:
                # Connection closed
                logger.warning("Connection closed while reading")
                return None
            data += chunk
        except socket.timeout:
            logger.warning("Socket timeout while reading")
            return None
        except Exception as e:
            logger.error(f"Error reading from socket: {e}")
            return None
    
    return data


def create_tcp_connection(host, port, timeout=30):
    """
    Create a TCP connection with proper error handling.
    
    Args:
        host: Target hostname/IP
        port: Target port
        timeout: Connection timeout in seconds
    
    Returns:
        socket: Connected socket, or None if failed
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        logger.info(f"Connected to {host}:{port}")
        return sock
    except Exception as e:
        logger.error(f"Failed to connect to {host}:{port}: {e}")
        return None


def close_connection(sock):
    """
    Safely close a socket connection.
    
    Args:
        sock: Socket to close
    """
    try:
        if sock:
            sock.close()
            logger.info("Connection closed")
    except Exception as e:
        logger.error(f"Error closing connection: {e}")


# Utility function to validate message types
def is_valid_message_type(msg_type):
    """Check if message type is valid."""
    return msg_type in [MSG_REQUEST, MSG_RESPONSE]


# Helper function for debugging
def format_http_message(data, max_length=200):
    """
    Format HTTP message for logging (truncate if too long).
    
    Args:
        data: HTTP message bytes
        max_length: Maximum length to display
    
    Returns:
        str: Formatted message for logging
    """
    try:
        decoded = data.decode('utf-8', errors='ignore')
        if len(decoded) > max_length:
            return decoded[:max_length] + '...'
        return decoded
    except:
        return f"<binary data: {len(data)} bytes>"