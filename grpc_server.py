import grpc
from concurrent import futures
import os
import json
import threading
import time
import uuid
import tempfile
import shutil
from typing import Dict, Set

import file_transfer_pb2
import file_transfer_pb2_grpc

# Enable gRPC verbose logging for debugging
os.environ['GRPC_VERBOSITY'] = 'info'


class FileTransferServicer(file_transfer_pb2_grpc.FileTransferServiceServicer):
    def __init__(self, node_name, disk_path, router_manager=None):
        self.node_name = node_name
        self.disk_path = disk_path
        self.router_manager = router_manager
        self.active_transfers: Dict[str, dict] = {}
        self.transfer_lock = threading.Lock()
        
    def StartTransfer(self, request, context):
        """Start a new file transfer session"""
        transfer_id = str(uuid.uuid4())
        
        with self.transfer_lock:
            self.active_transfers[transfer_id] = {
                'filename': request.filename,
                'file_size': request.file_size,
                'target_node': request.target_node,
                'sender_node': request.sender_node,
                'chunks_received': 0,
                'total_chunks': 0,
                'temp_file': None,
                'chunks_data': {}
            }
        
        return file_transfer_pb2.TransferResponse(
            success=True,
            message=f"Transfer session started for {request.filename}",
            transfer_id=transfer_id
        )
    
    def TransferChunk(self, request, context):
        """Receive a file chunk"""
        transfer_id = request.transfer_id
        
        with self.transfer_lock:
            if transfer_id not in self.active_transfers:
                return file_transfer_pb2.TransferResponse(
                    success=False,
                    message=f"Transfer session {transfer_id} not found"
                )
            
            transfer_info = self.active_transfers[transfer_id]
            transfer_info['chunks_data'][request.chunk_number] = request.data
            transfer_info['chunks_received'] += 1
            transfer_info['total_chunks'] = request.total_chunks
            
            # Check if all chunks received
            if transfer_info['chunks_received'] == request.total_chunks:
                # Reconstruct file
                try:
                    file_path = os.path.join(self.disk_path, request.filename)
                    with open(file_path, 'wb') as f:
                        for i in range(1, request.total_chunks + 1):
                            if i in transfer_info['chunks_data']:
                                f.write(transfer_info['chunks_data'][i])
                    
                    # Update virtual disk metadata
                    self._update_virtual_disk(request.filename, os.path.getsize(file_path))

                    # If this is a router and the file is for another node, forward it
                    if (self.router_manager and
                        request.target_node and
                        request.target_node != self.node_name):
                        self._forward_file_to_target(request.filename, request.target_node, request.sender_node)

                    return file_transfer_pb2.TransferResponse(
                        success=True,
                        message=f"File {request.filename} received successfully",
                        transfer_id=transfer_id
                    )
                except Exception as e:
                    return file_transfer_pb2.TransferResponse(
                        success=False,
                        message=f"Error writing file: {str(e)}",
                        transfer_id=transfer_id
                    )
            else:
                return file_transfer_pb2.TransferResponse(
                    success=True,
                    message=f"Chunk {request.chunk_number}/{request.total_chunks} received",
                    transfer_id=transfer_id
                )
    
    def CompleteTransfer(self, request, context):
        """Complete and cleanup a transfer session"""
        with self.transfer_lock:
            if request.transfer_id in self.active_transfers:
                del self.active_transfers[request.transfer_id]
        
        return file_transfer_pb2.TransferResponse(
            success=True,
            message=f"Transfer {request.transfer_id} completed"
        )
    
    def GetFileInfo(self, request, context):
        """Get information about a file"""
        file_path = os.path.join(self.disk_path, request.filename)
        
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            return file_transfer_pb2.FileInfoResponse(
                exists=True,
                size=size,
                message=f"File {request.filename} exists"
            )
        else:
            return file_transfer_pb2.FileInfoResponse(
                exists=False,
                size=0,
                message=f"File {request.filename} not found"
            )
    
    def ListFiles(self, request, context):
        """List files in the disk directory"""
        files = []
        try:
            for filename in os.listdir(self.disk_path):
                if filename != "disk_metadata.json":
                    file_path = os.path.join(self.disk_path, filename)
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        files.append(file_transfer_pb2.FileEntry(
                            name=filename,
                            size=size,
                            is_directory=False
                        ))
            
            return file_transfer_pb2.ListFilesResponse(
                files=files,
                message="Files listed successfully"
            )
        except Exception as e:
            return file_transfer_pb2.ListFilesResponse(
                files=[],
                message=f"Error listing files: {str(e)}"
            )
    
    def _update_virtual_disk(self, filename, size):
        """Update the virtual disk metadata"""
        metadata_path = os.path.join(self.disk_path, "disk_metadata.json")
        virtual_disk = {}
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    virtual_disk = json.load(f)
            except (json.JSONDecodeError, IOError):
                virtual_disk = {}
        
        virtual_disk[filename] = size
        
        try:
            with open(metadata_path, 'w') as f:
                json.dump(virtual_disk, f)
        except IOError as e:
            print(f"Error saving metadata: {e}")

    def _forward_file_to_target(self, filename, target_node, sender_node):
        """Forward a file from router to target node using gRPC"""
        if not self.router_manager:
            return

        try:
            from config import IP_MAP
            from grpc_client import GRPCClient

            # Find target node's gRPC port
            target_port = None
            for ip, info in IP_MAP.items():
                if info["node_name"] == target_node:
                    target_port = info["grpc_port"]
                    break

            if not target_port:
                print(f"Target node {target_node} not found in IP_MAP")
                return

            # Check if target node is active
            with self.router_manager.active_nodes_lock:
                if target_node not in self.router_manager.active_nodes:
                    print(f"Target node {target_node} is not active")
                    return

            # Forward file to target node
            file_path = os.path.join(self.disk_path, filename)
            client = GRPCClient()
            result = client.send_file(
                file_path=file_path,
                filename=filename,
                target_node=target_node,
                sender_node=sender_node,
                port=target_port
            )
            print(f"Forwarded {filename} from {sender_node} to {target_node}: {result}")

        except Exception as e:
            print(f"Error forwarding file to {target_node}: {e}")


class NodeManagementServicer(file_transfer_pb2_grpc.NodeManagementServiceServicer):
    def __init__(self, router_manager=None):
        self.router_manager = router_manager
        self.active_nodes: Set[str] = set()
        self.nodes_lock = threading.Lock()

    def RegisterNode(self, request, context):
        """Register a node as active"""
        with self.nodes_lock:
            self.active_nodes.add(request.node_name)

        # Also register with router manager if available
        if self.router_manager:
            with self.router_manager.active_nodes_lock:
                self.router_manager.active_nodes.add(request.node_name)
            print(f"Node {request.node_name} registered with router (gRPC)")

        return file_transfer_pb2.NodeResponse(
            success=True,
            message=f"Node {request.node_name} registered successfully"
        )

    def UnregisterNode(self, request, context):
        """Unregister a node"""
        with self.nodes_lock:
            self.active_nodes.discard(request.node_name)

        # Also unregister from router manager if available
        if self.router_manager:
            with self.router_manager.active_nodes_lock:
                self.router_manager.active_nodes.discard(request.node_name)
            print(f"Node {request.node_name} unregistered from router (gRPC)")

        return file_transfer_pb2.NodeResponse(
            success=True,
            message=f"Node {request.node_name} unregistered successfully"
        )

    def GetActiveNodes(self, request, context):
        """Get list of active nodes"""
        if self.router_manager:
            with self.router_manager.active_nodes_lock:
                nodes = list(self.router_manager.active_nodes)
        else:
            with self.nodes_lock:
                nodes = list(self.active_nodes)

        return file_transfer_pb2.ActiveNodesResponse(node_names=nodes)

    def HealthCheck(self, request, context):
        """Health check endpoint"""
        return file_transfer_pb2.HealthResponse(
            healthy=True,
            message="Service is healthy"
        )


class GRPCServer:
    def __init__(self, node_name, disk_path, port, is_router=False, router_manager=None):
        self.node_name = node_name
        self.disk_path = disk_path
        self.port = port
        self.is_router = is_router
        self.router_manager = router_manager
        self.server = None

        # Ensure disk path exists
        os.makedirs(disk_path, exist_ok=True)
    
    def start(self):
        """Start the gRPC server"""
        try:
            # Configure gRPC options for larger message sizes and Windows compatibility
            options = [
                ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
                ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
                ('grpc.max_message_length', 100 * 1024 * 1024),  # 100MB
                ('grpc.so_reuseport', 0),  # Disable SO_REUSEPORT for Windows
                ('grpc.so_reuseaddr', 1),  # Enable SO_REUSEADDR
            ]

            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), options=options)

            # Add file transfer service
            file_transfer_servicer = FileTransferServicer(self.node_name, self.disk_path, self.router_manager)
            file_transfer_pb2_grpc.add_FileTransferServiceServicer_to_server(
                file_transfer_servicer, self.server
            )

            # Add node management service (full service for router, minimal for nodes)
            if self.is_router:
                print(f"Adding full NodeManagementService for router {self.node_name}")
                node_mgmt_servicer = NodeManagementServicer(self.router_manager)
            else:
                print(f"Adding minimal NodeManagementService for node {self.node_name}")
                node_mgmt_servicer = NodeManagementServicer(None)  # No router manager for regular nodes

            file_transfer_pb2_grpc.add_NodeManagementServiceServicer_to_server(
                node_mgmt_servicer, self.server
            )

            # Try different binding addresses for Windows compatibility
            bind_addresses = [f'localhost:{self.port}', f'[::]:{self.port}', f'0.0.0.0:{self.port}']
            port_result = 0

            for listen_addr in bind_addresses:
                try:
                    print(f"Attempting to bind gRPC server for {self.node_name} to {listen_addr}")
                    port_result = self.server.add_insecure_port(listen_addr)
                    if port_result != 0:
                        print(f"Successfully bound to {listen_addr}")
                        break
                    else:
                        print(f"Failed to bind to {listen_addr}")
                except Exception as e:
                    print(f"Exception binding to {listen_addr}: {e}")

            if port_result == 0:
                print(f"Failed to bind to any address for port {self.port}")
                return None

            self.server.start()
            print(f"gRPC server started for {self.node_name} on port {self.port}")

            return self.server
        except Exception as e:
            print(f"Failed to start gRPC server for {self.node_name} on port {self.port}: {e}")
            print(f"Node {self.node_name} will continue without gRPC server")

            # Check if port is in use
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', self.port))
            if result == 0:
                print(f"Port {self.port} is already in use by another process")
            else:
                print(f"Port {self.port} appears to be available - other binding issue")
            sock.close()

            return None
    
    def stop(self):
        """Stop the gRPC server"""
        if self.server:
            self.server.stop(grace=5)
            print(f"gRPC server stopped for {self.node_name}")
    
    def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            self.server.wait_for_termination()
