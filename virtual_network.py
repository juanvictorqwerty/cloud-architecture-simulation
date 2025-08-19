import os
import threading
import math
import time
from config import IP_MAP, SERVER_IP, SERVER_GRPC_PORT
from grpc_client import GRPCClient

class VirtualNetwork:
    def __init__(self, manager=None):
        self.manager = manager
        self.ip_map = IP_MAP
        self.grpc_client = GRPCClient()
        self.bandwidth_bytes_per_sec = 125_000_000
        self.server_ip = SERVER_IP
        self.server_grpc_port = SERVER_GRPC_PORT
        self.server_disk_path = "./assets/server/"
        self.transfer_semaphore = threading.Semaphore(10)
        self.target_chunk_time = 0.1
        self.min_chunk_size = 1024 * 64
        self.max_chunk_size = 5 * 1024 * 1024

    # All FTP methods removed - using gRPC only

    def send_file_grpc(self, filename, source_ip, virtual_disk, target_node_name=None):
        """Send a file using gRPC instead of FTP"""
        if source_ip not in self.ip_map:
            return f"Error: Source IP {source_ip} not found"
        if filename not in virtual_disk:
            return f"Error: File {filename} not found on {source_ip}"

        source_node_name = self.ip_map[source_ip]["node_name"]
        source_path = os.path.join(self.ip_map[source_ip]["disk_path"], filename)

        # Use gRPC client to send file to router
        result = self.grpc_client.send_file(
            file_path=source_path,
            filename=filename,
            target_node=target_node_name,
            sender_node=source_node_name,
            port=self.server_grpc_port
        )
        return result

    # FTP forward_file method removed - using gRPC forwarding in router