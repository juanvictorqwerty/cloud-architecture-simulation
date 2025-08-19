import grpc
import os
import math
import time
from typing import Optional

import file_transfer_pb2
import file_transfer_pb2_grpc

# Enable gRPC verbose logging for debugging
os.environ['GRPC_VERBOSITY'] = 'info'


class GRPCClient:
    def __init__(self, target_host='localhost', target_port=None):
        self.target_host = target_host
        self.target_port = target_port
        self.channel = None
        self.file_transfer_stub = None
        self.node_mgmt_stub = None
        
        # Transfer parameters
        self.bandwidth_bytes_per_sec = 125_000_000
        self.target_chunk_time = 0.1
        self.min_chunk_size = 1024 * 64
        self.max_chunk_size = 5 * 1024 * 1024  # 5MB max chunk size
    
    def connect(self, port: int):
        """Connect to a gRPC server"""
        if self.channel:
            self.channel.close()

        # Configure gRPC options for larger message sizes
        options = [
            ('grpc.max_send_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_receive_message_length', 100 * 1024 * 1024),  # 100MB
            ('grpc.max_message_length', 100 * 1024 * 1024),  # 100MB
        ]

        target = f'{self.target_host}:{port}'
        self.channel = grpc.insecure_channel(target, options=options)
        self.file_transfer_stub = file_transfer_pb2_grpc.FileTransferServiceStub(self.channel)
        self.node_mgmt_stub = file_transfer_pb2_grpc.NodeManagementServiceStub(self.channel)

        # Test connection silently - try HealthCheck first (for routers), then ListFiles (for nodes)
        try:
            # Try HealthCheck first (works for routers)
            request = file_transfer_pb2.Empty()
            response = self.node_mgmt_stub.HealthCheck(request, timeout=5)
            return True
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.UNIMPLEMENTED:
                # HealthCheck not implemented, try ListFiles (for regular nodes)
                try:
                    request = file_transfer_pb2.ListFilesRequest(path="")
                    response = self.file_transfer_stub.ListFiles(request, timeout=5)
                    return True
                except grpc.RpcError:
                    return False
            else:
                return False
        except Exception:
            return False
    
    def disconnect(self):
        """Disconnect from the gRPC server"""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.file_transfer_stub = None
            self.node_mgmt_stub = None
    
    def _calculate_chunk_parameters(self, file_size):
        """Calculate optimized chunk size and number of chunks"""
        ideal_chunk_size = int(self.bandwidth_bytes_per_sec * self.target_chunk_time)
        chunk_size = max(self.min_chunk_size, min(ideal_chunk_size, self.max_chunk_size))
        
        if file_size <= self.min_chunk_size:
            chunk_size = file_size
            num_chunks = 1
        else:
            num_chunks = max(1, math.ceil(file_size / chunk_size))
            chunk_size = math.ceil(file_size / num_chunks)
        
        return chunk_size, num_chunks
    
    def send_file(self, file_path: str, filename: str, target_node: str, sender_node: str, port: int) -> str:
        """Send a file to a target node via gRPC"""
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found"
        
        file_size = os.path.getsize(file_path)
        
        # Connect to target
        if not self.connect(port):
            return f"Error: Could not connect to target on port {port}"
        
        try:
            # Start transfer session
            start_request = file_transfer_pb2.TransferRequest(
                filename=filename,
                file_size=file_size,
                target_node=target_node,
                sender_node=sender_node
            )
            
            start_response = self.file_transfer_stub.StartTransfer(start_request)
            if not start_response.success:
                return f"Error starting transfer: {start_response.message}"
            
            transfer_id = start_response.transfer_id
            
            # Calculate chunk parameters
            chunk_size, num_chunks = self._calculate_chunk_parameters(file_size)

            # Send file in chunks (silently)
            with open(file_path, 'rb') as f:
                for chunk_num in range(1, num_chunks + 1):
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break

                    chunk_request = file_transfer_pb2.FileChunk(
                        transfer_id=transfer_id,
                        chunk_number=chunk_num,
                        total_chunks=num_chunks,
                        data=chunk_data,
                        filename=filename,
                        target_node=target_node,
                        sender_node=sender_node
                    )

                    chunk_response = self.file_transfer_stub.TransferChunk(chunk_request)
                    if not chunk_response.success:
                        return f"Transfer failed"

                    # Simulate bandwidth limitation
                    time.sleep(len(chunk_data) / self.bandwidth_bytes_per_sec)

            # Complete transfer
            complete_request = file_transfer_pb2.CompleteTransferRequest(
                transfer_id=transfer_id,
                filename=filename,
                target_node=target_node
            )

            self.file_transfer_stub.CompleteTransfer(complete_request)

            return f"✓ {filename} sent to {target_node}"

        except grpc.RpcError:
            return f"✗ Transfer failed"
        except Exception:
            return f"✗ Transfer failed"
        finally:
            self.disconnect()
    
    def get_file_info(self, filename: str, port: int) -> Optional[dict]:
        """Get information about a file on the target node"""
        if not self.connect(port):
            return None
        
        try:
            request = file_transfer_pb2.FileInfoRequest(filename=filename)
            response = self.file_transfer_stub.GetFileInfo(request)
            
            return {
                'exists': response.exists,
                'size': response.size,
                'message': response.message
            }
        except grpc.RpcError:
            return None
        finally:
            self.disconnect()
    
    def list_files(self, port: int) -> Optional[list]:
        """List files on the target node"""
        if not self.connect(port):
            return None
        
        try:
            request = file_transfer_pb2.ListFilesRequest(path="")
            response = self.file_transfer_stub.ListFiles(request)
            
            files = []
            for file_entry in response.files:
                files.append({
                    'name': file_entry.name,
                    'size': file_entry.size,
                    'is_directory': file_entry.is_directory
                })
            
            return files
        except grpc.RpcError:
            return None
        finally:
            self.disconnect()
    
    def register_node(self, node_name: str, ip_address: str, port: int, router_port: int) -> bool:
        """Register a node with the router"""
        if not self.connect(router_port):
            return False
        
        try:
            request = file_transfer_pb2.NodeRegistration(
                node_name=node_name,
                ip_address=ip_address,
                port=port
            )
            
            response = self.node_mgmt_stub.RegisterNode(request)
            return response.success
        except grpc.RpcError:
            return False
        finally:
            self.disconnect()
    
    def unregister_node(self, node_name: str, ip_address: str, port: int, router_port: int) -> bool:
        """Unregister a node from the router"""
        if not self.connect(router_port):
            return False
        
        try:
            request = file_transfer_pb2.NodeRegistration(
                node_name=node_name,
                ip_address=ip_address,
                port=port
            )
            
            response = self.node_mgmt_stub.UnregisterNode(request)
            return response.success
        except grpc.RpcError:
            return False
        finally:
            self.disconnect()
    
    def get_active_nodes(self, router_port: int) -> Optional[list]:
        """Get list of active nodes from the router"""
        if not self.connect(router_port):
            return None
        
        try:
            request = file_transfer_pb2.Empty()
            response = self.node_mgmt_stub.GetActiveNodes(request)
            return list(response.node_names)
        except grpc.RpcError:
            return None
        finally:
            self.disconnect()
