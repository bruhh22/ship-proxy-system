# Ship Proxy System

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Enabled-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📖 Introduction

This project implements a cost-saving proxy system for a cruise ship ("Royal Caribs") that minimizes satellite internet costs by reusing a single persistent TCP connection for all outbound HTTP/HTTPS requests.

**The Problem:** Satellite internet providers charge based on the number of TCP connections, not data transferred. Opening a new TCP connection for every HTTP request from passengers becomes expensive.

**The Solution:** Route all HTTP/HTTPS requests through a single persistent TCP connection between a Ship Proxy (on the ship) and an Offshore Proxy (remote server), achieving significant cost savings.

Instead of opening a new TCP connection for every request, the Ship Proxy forwards all browser/curl requests sequentially over one TCP connection to the Offshore Proxy, which then forwards them to the internet.

## 🎯 System Objectives

### Ship Proxy (Client)
- Runs inside the ship's local network
- Listens on port 8080 for HTTP proxy requests
- Accepts proxy requests from browsers, curl, or other tools
- Queues and forwards requests sequentially to the offshore proxy
- Maintains a single persistent TCP connection to offshore proxy

### Offshore Proxy (Server)  
- Runs remotely (on land-based servers)
- Listens on port 9999 for ship proxy connections
- Receives requests via the persistent TCP connection
- Forwards them to real internet servers using standard HTTP/HTTPS
- Sends back responses to the ship proxy through the same connection

### Key Features
✅ **Sequential request handling** (one at a time for reliability)  
✅ **HTTP and HTTPS support** (including CONNECT tunneling)  
✅ **All HTTP methods** supported (GET, POST, PUT, DELETE, HEAD, OPTIONS, etc.)  
✅ **Works with curl** on Mac/Linux/Windows  
✅ **Browser proxy configuration** supported  
✅ **Dockerized** for easy deployment  
✅ **Custom framing protocol** for TCP multiplexing  
✅ **Automatic reconnection** on connection failures  

## 🏗️ System Design

### Architecture Flow
```
Browser/Curl → Ship Proxy (8080) → Single TCP Connection → Offshore Proxy (9999) → Target Internet Server
                    ↓                                                ↓
               Queue Requests                                  Forward to Internet
               Process Sequentially                           Return Responses
```

### Key Components
1. **Custom Framing Protocol**: Length-prefixed messages to multiplex requests/responses over single TCP connection
2. **Sequential Processing**: FIFO queue ensures requests are handled one at a time
3. **HTTPS Tunneling**: CONNECT method support for secure connections
4. **Persistent Connection**: Single TCP connection with automatic reconnection
5. **Proxy Compatibility**: Standard HTTP proxy interface for browser/tool compatibility

### Challenges Solved
- **TCP Multiplexing**: Custom binary protocol frames multiple HTTP requests/responses
- **Sequential Processing**: Queue-based system ensures reliability over unstable satellite links  
- **HTTPS Support**: CONNECT method tunneling for secure connections
- **Connection Management**: Persistent TCP with reconnection logic
- **Error Handling**: Graceful failure handling and recovery

## 🗂️ Project Structure

```
ship-proxy-system/
│
├── client/                     # Ship Proxy (runs inside the ship)
│   ├── client.py               # Main Python file for Ship Proxy
│   ├── Dockerfile              # Dockerfile for building Ship Proxy image
│   ├── requirements.txt        # Python dependencies
│   └── __init__.py             # Package marker
│
├── server/                     # Offshore Proxy (runs remotely)
│   ├── server.py               # Main Python file for Offshore Proxy
│   ├── Dockerfile              # Dockerfile for building Offshore Proxy image
│   ├── requirements.txt        # Python dependencies
│   └── __init__.py             # Package marker
│
├── utils/                      # Shared helper functions
│   ├── protocol.py             # Custom framing protocol implementation
│   └── __init__.py             # Package marker
│
├── tests/                      # Unit/integration tests
│   ├── test_http_requests.py   # Test HTTP methods (GET/POST/PUT/DELETE)
│   ├── test_https_connect.py   # Test HTTPS tunneling (CONNECT method)
│   └── __init__.py             # Package marker
│
├── docker-compose.yml          # Orchestrate client + server locally
├── README.md                   # This documentation file
├── LICENSE                     # License information
└── .gitignore                  # Git ignore patterns
```

## ⚙️ Technologies Used

### Programming Language
- **Python 3.12**: Lightweight, excellent for networking tasks, beginner-friendly

### Core Libraries (Python Standard Library)
- `socket` → Raw TCP communication between Ship and Offshore proxies
- `http.server` → Ship Proxy HTTP interface (listening on port 8080)
- `http.client` → Offshore Proxy forwarding to target servers
- `ssl` → HTTPS tunneling support (CONNECT method)
- `queue` → Sequential request processing (FIFO)
- `threading` → Concurrent handling of incoming requests
- `logging` → Debugging and monitoring
- `argparse` → Command-line argument parsing

### Containerization
- **Docker**: `python:3.12-slim` base image for minimal footprint
- **Docker Compose**: Orchestration for local development and testing

### Communication Protocol
- **Custom Binary Framing**:
  - 4 bytes → payload length (uint32, big-endian)
  - 1 byte → message type (0=request, 1=response)  
  - Payload → raw HTTP request/response bytes

## 🔌 Installation & Setup

### Prerequisites
- Docker and Docker Compose installed
- Git for cloning the repository
- (Optional) Python 3.12+ for local development

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/<your-username>/ship-proxy-system.git
cd ship-proxy-system
```

### 2️⃣ Build Docker Images

#### Build Ship Proxy (Client)
```bash
docker build -t <your-dockerhub-username>/ship-proxy -f client/Dockerfile .
```

#### Build Offshore Proxy (Server)
```bash
docker build -t <your-dockerhub-username>/offshore-proxy -f server/Dockerfile .
```

#### Or Build Both at Once
```bash
docker-compose build
```

## ▶️ Running the System

### Option A: Run with Docker Compose (Recommended)
```bash
# Start both services
docker-compose up --build

# Start in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

This automatically:
- Starts the Offshore Proxy on port 9999
- Starts the Ship Proxy on port 8080  
- Configures internal networking between them
- Sets up health checks and auto-restart

### Option B: Run Containers Individually

#### Start Offshore Proxy
```bash
docker run -p 9999:9999 --name offshore-proxy <your-dockerhub-username>/offshore-proxy
```

#### Start Ship Proxy
```bash
docker run -p 8080:8080 --name ship-proxy \
  -e OFFSHORE_HOST=<offshore-ip-or-hostname> \
  <your-dockerhub-username>/ship-proxy
```

**Environment Variables:**
- `OFFSHORE_HOST`: IP/hostname of offshore proxy (use `host.docker.internal` for local Docker)
- `OFFSHORE_PORT`: Port of offshore proxy (default: 9999)
- `LISTEN_PORT`: Ship proxy listen port (default: 8080)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

### Option C: Run Locally (Development)

#### Start Offshore Proxy
```bash
cd server
python server.py
```

#### Start Ship Proxy  
```bash
cd client
python client.py --offshore-host=localhost --offshore-port=9999
```

## ✅ Testing the System

### Browser Configuration
Configure your browser to use HTTP proxy:
- **HTTP Proxy**: `localhost:8080`
- **HTTPS Proxy**: `localhost:8080`  
- **No authentication required**

### Command Line Testing

#### Basic HTTP Request
```bash
curl -x http://localhost:8080 http://httpforever.com/
```

#### HTTPS Request
```bash
curl -x http://localhost:8080 https://example.com/
```

#### Different HTTP Methods
```bash
# POST request
curl -x http://localhost:8080 -X POST -d "name=test&data=value" http://httpbin.org/post

# PUT request  
curl -x http://localhost:8080 -X PUT -d "update=data" http://httpbin.org/put

# DELETE request
curl -x http://localhost:8080 -X DELETE http://httpbin.org/delete

# GET with parameters
curl -x http://localhost:8080 "http://httpbin.org/get?param1=value1&param2=value2"
```

#### Test Sequential Processing
```bash
# Run multiple requests in parallel - they will be processed sequentially
for i in {1..5}; do 
  curl -x http://localhost:8080 "http://httpbin.org/get?request=$i" & 
done
wait
```

#### Windows Testing
```cmd
curl.exe -x http://localhost:8080 http://httpforever.com/
```

### Expected Behavior
- All requests should return valid responses
- Multiple concurrent requests are processed sequentially (one at a time)
- Both HTTP and HTTPS requests work correctly
- Browser proxy configuration works for web browsing

## 🧪 Development & Testing

### Run Automated Tests
```bash
# Install test dependencies
pip install pytest requests

# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_http_requests.py -v
pytest tests/test_https_connect.py -v

# Run with coverage
pytest tests/ --cov=client --cov=server --cov=utils

# Run specific test class
pytest tests/test_http_requests.py::TestBasicHTTPMethods -v
```

### Local Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies (optional)
pip install pytest requests black flake8

# Run linting
black client/ server/ utils/ tests/
flake8 client/ server/ utils/ tests/
```

### Debugging
- Set `LOG_LEVEL=DEBUG` for detailed logging
- Use `docker-compose logs` to view container output  
- Monitor TCP traffic with tools like Wireshark or tcpdump
- Check health status: `docker-compose ps`

## 📦 Deployment

### Push to Docker Hub
```bash
# Tag images
docker tag ship-proxy <your-dockerhub-username>/ship-proxy:latest
docker tag offshore-proxy <your-dockerhub-username>/offshore-proxy:latest

# Push images
docker push <your-dockerhub-username>/ship-proxy:latest
docker push <your-dockerhub-username>/offshore-proxy:latest
```

### Production Deployment Commands

#### Pull and Run Ship Proxy
```bash
docker pull <your-dockerhub-username>/ship-proxy:latest
docker run -d -p 8080:8080 \
  -e OFFSHORE_HOST=<production-offshore-host> \
  -e OFFSHORE_PORT=9999 \
  --name ship-proxy \
  --restart unless-stopped \
  <your-dockerhub-username>/ship-proxy:latest
```

#### Pull and Run Offshore Proxy
```bash
docker pull <your-dockerhub-username>/offshore-proxy:latest
docker run -d -p 9999:9999 \
  --name offshore-proxy \
  --restart unless-stopped \
  <your-dockerhub-username>/offshore-proxy:latest
```

### Environment-Specific Configuration
```bash
# Development
OFFSHORE_HOST=localhost
LOG_LEVEL=DEBUG

# Staging  
OFFSHORE_HOST=staging-proxy.example.com
LOG_LEVEL=INFO

# Production
OFFSHORE_HOST=proxy.shipinternet.com
LOG_LEVEL=WARNING
```

## 🚨 Troubleshooting

### Common Issues

#### Ship Proxy Can't Connect to Offshore Proxy
```bash
# Check if offshore proxy is running
docker ps | grep offshore-proxy

# Check logs
docker-compose logs offshore-proxy

# Test connectivity
telnet <offshore-host> 9999
```

#### Requests Not Working Through Proxy
```bash
# Verify proxy is listening
netstat -an | grep 8080

# Check ship proxy logs
docker-compose logs ship-proxy

# Test direct connection
curl -v -x http://localhost:8080 http://example.com/
```

#### HTTPS Not Working
```bash
# Check CONNECT method support
curl -v -x http://localhost:8080 https://example.com/

# Verify SSL handling in logs
docker-compose logs | grep -i ssl
```

### Health Checks
```bash
# Check service health
docker-compose ps

# Manual health check
curl -f http://localhost:8080 || echo "Ship proxy not healthy"
telnet localhost 9999 || echo "Offshore proxy not accessible"
```

## 🚀 Performance & Limitations

### Performance Characteristics
- **Sequential Processing**: Requests are handled one at a time for reliability
- **Single TCP Connection**: Reduces connection overhead but may introduce latency
- **Memory Usage**: Minimal - uses Python standard library only
- **Throughput**: Optimized for reliability over speed (suitable for satellite connections)

### Known Limitations
- **Sequential Processing**: May introduce delays with high request volumes
- **Single Point of Failure**: One TCP connection handles all traffic
- **No Caching**: Each request goes to the target server (can be enhanced)
- **Basic Error Handling**: Simple retry logic (can be improved)

### Recommended Improvements for Production
- **Connection Pooling**: Multiple TCP connections for higher throughput
- **Caching Layer**: Cache common responses to reduce internet requests
- **Load Balancing**: Multiple offshore proxies for redundancy
- **TLS Encryption**: Secure communication between ship and offshore proxies
- **Monitoring**: Metrics collection and alerting
- **Authentication**: Access control for proxy usage

## 📋 Assignment Requirements Checklist

✅ **Source code uploaded to GitHub**  
✅ **Docker images built and can be published**  
✅ **Commands provided to run client and server via Docker**  
✅ **Client exposes port 8080 for incoming connections**  
✅ **Mac/Linux**: `curl -x http://localhost:8080 http://httpforever.com/` works  
✅ **Windows**: `curl.exe -x http://localhost:8080 http://httpforever.com/` works  
✅ **Multiple curl calls respond consistently**  
✅ **All HTTP methods supported** (GET/POST/PUT/DELETE/etc.)  
✅ **Sequential processing** (requests handled one by one)  
✅ **HTTPS support** via CONNECT method  
✅ **Browser proxy configuration** compatibility  

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Ship Proxy System Team**
- GitHub: [@your-username](https://github.com/your-username)
- Docker Hub: [your-dockerhub-username](https://hub.docker.com/u/your-dockerhub-username)

## 🙏 Acknowledgments

- Cruise ship "Royal Caribs" for the cost optimization challenge
- Python community for excellent networking libraries
- Docker for containerization platform
- Contributors and testers

---

**Note**: This system is designed for educational/demonstration purposes. For production deployment on actual cruise ships, additional security, monitoring, and redundancy measures should be implemented.