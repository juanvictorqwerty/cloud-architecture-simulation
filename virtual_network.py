import os
import ftplib
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import threading
import tempfile
import math
import time
import re
import shutil
from node_ftp_handler import NodeFTPHandler
from config import IP_MAP, SERVER_IP, SERVER_SOCKET_PORT, SERVER_FTP_PORT, SERVER_GRPC_PORT
from grpc_client import GRPCClient

class VirtualNetwork:
    def __init__(self, manager=None):
        self.manager = manager
        self.ip_map = IP_MAP
        self.ftp_servers = {}
        self.grpc_client = GRPCClient()
        self.bandwidth_bytes_per_sec = 125_000_000
        self.header_size = 32
        self.server_ip = SERVER_IP
        self.server_port = SERVER_SOCKET_PORT
        self.server_ftp_port = SERVER_FTP_PORT
        self.server_grpc_port = SERVER_GRPC_PORT
        self.server_disk_path = "./assets/server/"
        self.transfer_semaphore = threading.Semaphore(10)
        self.target_chunk_time = 0.1
        self.min_chunk_size = 1024 * 64
        self.max_chunk_size = 10*1024 * 1024

    def start_ftp_server(self, node, ip_address, ftp_port, disk_path):
        """Start an FTP server for a node."""
        authorizer = DummyAuthorizer()
        authorizer.add_user("user", "password", disk_path, perm="elradfmw")
        handler = NodeFTPHandler
        handler.authorizer = authorizer
        ftp_server = FTPServer(("0.0.0.0", ftp_port), handler)
        ftp_server.node = node
        self.ftp_servers[ip_address] = ftp_server
        ftp_thread = threading.Thread(target=ftp_server.serve_forever, daemon=True)
        ftp_thread.start()
        print(f"FTP server started on {ip_address}:{ftp_port}")

    def stop_ftp_server(self, ip_address):
        """Stop the FTP server for a given IP address."""
        if ip_address in self.ftp_servers:
            self.ftp_servers[ip_address].close_all()
            print(f"FTP server stopped for {ip_address}")
            del self.ftp_servers[ip_address]

    def _get_unique_filename(self, filename, target_ip):
        """
        Returns the original filename.
        The receiving node is responsible for ensuring uniqueness if needed.
        """
        return filename
            
    def _calculate_chunk_parameters(self, file_size):
        """Calculate optimized chunk size and number of chunks."""
        ideal_chunk_size = int(self.bandwidth_bytes_per_sec * self.target_chunk_time)
        chunk_size = max(self.min_chunk_size, min(ideal_chunk_size, self.max_chunk_size))
        if file_size <= self.min_chunk_size:
            chunk_size = file_size
            num_chunks = 1
        else:
            num_chunks = max(1, math.ceil(file_size / chunk_size))
            chunk_size = math.ceil(file_size / num_chunks)
        return chunk_size, num_chunks

    def _execute_chunked_transfer(self, ftp, source_path, size, target_filename, target_node_name=None, sender_node_name=None):
        """Helper to perform the actual chunked FTP transfer, sending each chunk as a new file."""
        start_time = time.time()
        print(f"Transfer of {target_filename} started at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

        chunk_size, num_chunks = self._calculate_chunk_parameters(size)
        sent_bytes = 0
        chunk_count = 0
        try:
            with open(source_path, 'rb') as f:
                while chunk_count < num_chunks and sent_bytes < size:
                    chunk_count += 1
                    remaining_bytes = size - sent_bytes
                    current_chunk_size = min(chunk_size, remaining_bytes)
                    chunk = f.read(current_chunk_size)
                    if not chunk:
                        break

                    header_str = f"CHUNK:{chunk_count}:{current_chunk_size}:{num_chunks}"
                    if target_node_name:
                        header_str += f":{target_node_name}"
                    if sender_node_name:
                        header_str += f":{sender_node_name}"
                    header_str += "\n"

                    header = header_str.encode().ljust(self.header_size, b'\0')
                    chunk_with_header = header + chunk

                    temp_file = tempfile.NamedTemporaryFile(delete=False)
                    temp_file_path = temp_file.name
                    try:
                        temp_file.write(chunk_with_header)
                        temp_file.close()
                        with open(temp_file_path, 'rb') as temp_f:
                            ftp.storbinary(f"STOR {target_filename}", temp_f)
                        sent_bytes += current_chunk_size
                        time.sleep(current_chunk_size / self.bandwidth_bytes_per_sec)
                    finally:
                        try:
                            os.unlink(temp_file_path)
                        except OSError:
                            pass
        except ftplib.error_perm as e:
            raise Exception(f"FTP error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error in chunked transfer: {e}")

        end_time = time.time()
        print(f"Transfer of {target_filename} completed in {end_time - start_time:.2f} seconds")

    def send_file(self, filename, source_ip, virtual_disk, target_node_name=None):
        """Send a file from source_ip to the router."""
        if source_ip not in self.ip_map:
            return f"Error: Source IP {source_ip} not found"
        if filename not in virtual_disk:
            return f"Error: File {filename} not found on {source_ip}"

        source_node_name = self.ip_map[source_ip]["node_name"]
        target_ip = self.server_ip
        source_path = os.path.join(self.ip_map[source_ip]["disk_path"], filename)
        size = virtual_disk[filename]

        try:
            target_filename = filename # Router will receive with original name
            ftp = ftplib.FTP()
            ftp.connect(host="127.0.0.1", port=self.server_ftp_port)
            ftp.login(user="user", passwd="password")
            self._execute_chunked_transfer(ftp, source_path, size,
                                target_filename,   #  <<< guaranteed not None
                                target_node_name,
                                source_node_name)
            ftp.quit()
            return f"Sent {filename} ({size} bytes) to {target_ip} for forwarding to {target_node_name}"
        except Exception as e:
            return f"Error sending file to {target_ip}: {e}"

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

    def forward_file(self, folder_name, target_node_name, *, is_replication=False, original_filename=None):
        """Forward pending files to the target node in a separate thread."""
        def forward_task(folder_name, target_ip, file_path, size, original_filename, sender_node):
            with self.transfer_semaphore:
                try:
                    if target_node_name not in self.manager.active_nodes:
                        print(f"Error: Target node {target_node_name} is not active, transfer failed for {original_filename}")
                        return
                    target_filename = original_filename # Node will receive with original name
                    ftp = ftplib.FTP()
                    ftp.connect(host="127.0.0.1", port=self.ip_map[target_ip]["ftp_port"])
                    ftp.login(user="user", passwd="password")
                    self._execute_chunked_transfer(ftp, file_path, size, target_filename, target_node_name, sender_node)
                    ftp.quit()
                    with self.manager.pending_files_lock:
                        if folder_name in self.manager.pending_files:
                            del self.manager.pending_files[folder_name]
                    shutil.rmtree(os.path.dirname(file_path))
                    print(f"Deleted folder {folder_name} from server after forwarding")
                except Exception as e:
                    print(f"Error forwarding file {original_filename} to {target_ip}: {e}")

        target_ip = None
        for ip, info in self.ip_map.items():
            if info["node_name"] == target_node_name:
                target_ip = ip
                break
        if not target_ip:
            print(f"Error: Target node {target_node_name} not found")
            return

        files_to_forward = []
        with self.manager.pending_files_lock:
            for fname, (tname, fname_orig, sender_node) in list(self.manager.pending_files.items()):
                if tname == target_node_name:
                    file_path = os.path.join(self.server_disk_path, fname, fname_orig)
                    if os.path.exists(file_path):
                        size = os.path.getsize(file_path)
                        files_to_forward.append((fname, file_path, size, fname_orig, sender_node))

        for fname, file_path, size, fname_orig, sender_node in files_to_forward:
            threading.Thread(target=forward_task, args=(fname, target_ip, file_path, size, fname_orig, sender_node), daemon=True).start()