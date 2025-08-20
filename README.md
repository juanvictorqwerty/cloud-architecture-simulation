# Cloud Architecture Simulation

A sophisticated distributed file system that simulates real-world cloud storage and networking behaviors with gRPC communication, chunked file transfers, and network topology awareness.

## 📋 Project Overview

The Cloud Architecture Simulation implements a microservices architecture that demonstrates enterprise-level distributed systems concepts. It features a router-based file transfer system with redundant cloud storage, network topology constraints, and real-time monitoring capabilities.

## 🏗️ System Architecture

### Core Components

#### Router (Central Coordinator)
- **Purpose**: Central hub for all file transfers and node management
- **Ports**: 8000 (gRPC), 9999 (Socket)
- **Responsibilities**:
  - Route files between nodes based on network topology
  - Track active nodes and their status
  - Provide real-time transfer monitoring
  - Maintain comprehensive logs of all operations
  - Forward files to target destinations

#### Regular Nodes (node1-node5)
- **Purpose**: Simulate individual computers or devices in the network
- **Ports**: 8001-8005 (gRPC)
- **Capabilities**:
  - Store and manage local files
  - Send files to other nodes (with link restrictions)
  - Upload files to cloud storage
  - Download files from cloud storage
  - Respect network topology constraints

#### Cloud Nodes (cloud1-cloud3)
- **Purpose**: Simulate cloud storage services with redundancy
- **Ports**: 8011-8013 (gRPC)
- **Features**:
  - Provide distributed storage across multiple instances
  - Accept uploads from any node (no link restrictions)
  - Serve download requests
  - Maintain file metadata and integrity

## 🔗 Network Topology & Link Management

### Link-Based Communication
- **Concept**: Nodes can only communicate if they share a network link
- **Implementation**: Uses LinksManager to validate transfer permissions
- **Rules**:
  - Node-to-node transfers require shared links
  - Cloud access is always permitted (no link restrictions)
  - Router enforces topology constraints

### Transfer Types
1. **Upload**: Any node → All cloud nodes (always allowed)
2. **Send**: Node → Node (requires link validation)
3. **Download**: Cloud → Node (always allowed)

## 📡 Communication Protocol

### gRPC Implementation
- **Protocol**: HTTP/2-based gRPC with Protocol Buffers
- **Services**:
  - `FileTransferService`: Handles file operations
  - `NodeManagementService`: Manages node registration

### Message Types
- **FileChunk**: Individual data segments with metadata
- **TransferRequest**: Initiates file transfer sessions
- **NodeRegistration**: Registers/unregisters nodes with router

## 📦 File Transfer Mechanism

### Chunked Transfer System
- **Chunk Size Range**: 64KB (minimum) to 5MB (maximum)
- **Optimization**: Calculates optimal chunk size based on file size
- **Bandwidth Simulation**: 125MB/s with realistic timing delays
- **Progress Tracking**: Real-time chunk-by-chunk monitoring

### Transfer Process
1. **Session Initiation**: Client requests transfer session
2. **Chunking**: File split into optimally-sized chunks
3. **Sequential Transfer**: Chunks sent with metadata
4. **Reconstruction**: Server reassembles original file
5. **Forwarding**: Router forwards to final destination if needed

## 🖥️ User Interface

### Client Commands
- `touch filename size`: Create file with specified size (MB)
- `upload filename`: Upload file to all cloud nodes
- `send filename target`: Send file to specific node
- `download filename`: Download file from cloud storage
- `ls`: List local files
- `start`/`stop`: Control node status

### Router Display
- **Transfer Start**: `filename: starting`
- **Chunk Progress**: `filename: 1/20`, `filename: 2/20`
- **Completion**: `filename: complete`
- **Forwarding**: `filename: forwarding to target`

## 📊 Monitoring & Logging

### Client Experience
- **Minimal Output**: Clean, essential information only
- **Status Indicators**: ✓ (success), ✗ (failure), ⏳ (progress)
- **Concise Messages**: Brief, actionable feedback

### Router Monitoring
- **Real-time Progress**: Live chunk transfer visualization
- **Comprehensive Logs**: Detailed operation history
- **Error Tracking**: Complete exception information
- **Performance Metrics**: Transfer speeds and file sizes

## 🔧 Configuration Management

### Port Allocation
```
Router:     8000 (gRPC), 9999 (Socket)
Nodes:      8001-8005 (node1-node5)
Clouds:     8011-8013 (cloud1-cloud3)
```

### File Storage
```
Router:     ./assets/server/
Nodes:      ./assets/node1/ through ./assets/node5/
Clouds:     ./assets/cloud1/ through ./assets/cloud3/
```

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Required packages: `grpcio>=1.50.0`, `grpcio-tools>=1.50.0`, `protobuf>=4.21.0`

### Installation
```bash
pip install grpcio grpcio-tools protobuf
```

### System Startup
1. **Start Router**: `python router.py`
2. **Start Cloud Nodes**: `python cloud1.py`, `python cloud2.py`, `python cloud3.py`
3. **Start Regular Nodes**: `python node1.py`, `python node2.py`, etc.

### Typical Workflow
```bash
# In node1 terminal
touch document.pdf 5        # Create 5MB file
upload document.pdf         # Upload to all 3 clouds
send document.pdf node2     # Send to node2 (if link exists)

# In node2 terminal
download document.pdf       # Download from cloud
ls                         # List local files
```
## 🛡️ Error Handling & Reliability

### Fault Tolerance
- **Graceful Degradation**: System continues operating with partial failures
- **Redundant Storage**: Files stored across multiple cloud nodes
- **Connection Recovery**: Automatic retry mechanisms
- **Validation**: Comprehensive input and state checking

### Error Scenarios
- **Network Failures**: Handled with appropriate error messages
- **Missing Files**: Clear feedback about file availability
- **Link Restrictions**: Informative messages about topology constraints
- **Node Unavailability**: Graceful handling of offline nodes

## 📈 Performance Characteristics

### Scalability Features
- **Horizontal Scaling**: Easy addition of new nodes
- **Load Distribution**: Multiple cloud nodes share storage load
- **Efficient Chunking**: Optimized for large file transfers
- **Concurrent Operations**: Multiple transfers can occur simultaneously

### Optimization Strategies
- **Adaptive Chunk Sizing**: Automatically optimizes for file size
- **Bandwidth Simulation**: Realistic network behavior modeling
- **Memory Efficiency**: Streaming transfers without full file loading
- **Protocol Efficiency**: gRPC provides high-performance communication

## 🎯 Use Cases & Applications

### Educational Applications
- **Distributed Systems Learning**: Hands-on experience with real concepts
- **Network Protocol Understanding**: gRPC and chunked transfer implementation
- **System Design Practice**: Microservices architecture patterns
- **Performance Analysis**: Transfer optimization and monitoring

### Research Applications
- **Network Topology Studies**: Link-based communication modeling
- **File Distribution Algorithms**: Redundancy and availability research
- **Performance Benchmarking**: Transfer speed and efficiency analysis
- **Fault Tolerance Testing**: System behavior under various failure conditions

## 🔮 Technical Innovation

### Modern Technologies
- **gRPC**: Industry-standard high-performance RPC framework
- **Protocol Buffers**: Efficient binary serialization
- **Microservices**: Scalable, maintainable architecture
- **Event-Driven Design**: Real-time monitoring and feedback

### Advanced Features
- **Dynamic Chunk Optimization**: Intelligent transfer sizing
- **Network Topology Awareness**: Link-based routing decisions
- **Real-time Monitoring**: Live transfer visualization
- **Comprehensive Logging**: Enterprise-grade operational visibility

## 📚 Project Complexity

### Academic Level: Advanced Undergraduate / Graduate
This project demonstrates:
- **Distributed Systems Design**
- **Network Protocol Implementation**
- **Concurrent Programming**
- **Service-Oriented Architecture**
- **Real-time System Monitoring**
- **Enterprise-grade Error Handling**

### Industry Relevance
Similar to real-world systems like:
- Google Drive/Dropbox (distributed file storage)
- Netflix CDN (content distribution)
- Kubernetes (container orchestration)
- Apache Kafka (distributed messaging)

## 🏢 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Router (Port 8000)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   gRPC      │  │   Socket    │  │   Logging   │     │
│  │  Service    │  │   Server    │  │   System    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
           │                    │                    │
    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
    │   Node1     │     │   Node2     │     │   Cloud     │
    │  (8001)     │     │  (8002)     │     │ (8011-8013) │
    └─────────────┘     └─────────────┘     └─────────────┘
```

## 📄 License

This project is designed for educational and research purposes, demonstrating advanced distributed systems concepts and modern software engineering practices.

---

*A comprehensive distributed file system simulation showcasing enterprise-level software engineering and modern distributed systems concepts.*
