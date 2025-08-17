import os
import threading
import socket
import logging
import json
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from virtual_network import VirtualNetwork
from router_ftp_handler import RouterFTPHandler
from config import SERVER_IP, SERVER_FTP_PORT, SERVER_SOCKET_PORT, SERVER_DISK_PATH

class RouterManager:
    def __init__(self):
        self.ip_address = SERVER_IP
        self.ftp_port = SERVER_FTP_PORT
        self.disk_path = SERVER_DISK_PATH
        self.network = VirtualNetwork(self)
        self.pending_files = {}
        self.pending_files_lock = threading.Lock()
        self.ftp_server = None
        self.socket_server = None
        self.socket_port = SERVER_SOCKET_PORT
        self.active_nodes = set()
        self.active_nodes_lock = threading.Lock()
        self.logger = None
        self._setup_logging()

    def _setup_logging(self):
        """Sets up centralized logging for the router."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("router.log"),
                logging.StreamHandler()
            ])
        self.logger = logging.getLogger("RouterManager")

    def start(self):
        """Start the FTP server and socket server."""
        authorizer = DummyAuthorizer()
        authorizer.add_user("user", "password", self.disk_path, perm="elradfmw")
        handler = RouterFTPHandler
        handler.authorizer = authorizer
        self.ftp_server = FTPServer(("0.0.0.0", self.ftp_port), handler)
        self.ftp_server.node = None
        self.ftp_server.manager = self
        ftp_thread = threading.Thread(target=self.ftp_server.serve_forever, daemon=True)
        ftp_thread.start()
        print(f"FTP server started on {self.ip_address}:{self.ftp_port}")

        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_server.bind(("0.0.0.0", self.socket_port))
        self.socket_server.listen(10)
        socket_thread = threading.Thread(target=self._handle_socket_connections, daemon=True)
        socket_thread.start()
        print(f"Socket server started on {self.ip_address}:{self.socket_port}")

    def stop(self):
        """Stop the FTP server and socket server."""
        if self.ftp_server:
            self.ftp_server.close_all()
            self.logger.info(f"FTP server stopped for {self.ip_address}")
        if self.socket_server:
            self.socket_server.close()
            self.logger.info(f"Socket server stopped for {self.ip_address}")

    def _handle_socket_connections(self):
        """Handle incoming socket connections from nodes."""
        while True:
            try:
                client_socket, addr = self.socket_server.accept()
                threading.Thread(target=self._process_socket_message, args=(client_socket,), daemon=True).start()
            except Exception as e:
                self.logger.error(f"Socket server error: {e}", exc_info=True)
                break

    def _process_socket_message(self, client_socket):
        """Process node availability messages."""
        try:
            data = client_socket.recv(1024).decode()
            message = json.loads(data)
            if message.get("action") == "node_started":
                node_name = message.get("node_name")
                self.logger.info(f"Node {node_name} started, checking for pending files")
                with self.active_nodes_lock:
                    self.active_nodes.add(node_name)
                self.network.forward_file(None, node_name)
            client_socket.close()
        except Exception as e:
            self.logger.error(f"Error processing socket message: {e}", exc_info=True)
            client_socket.close()

    def check_node_and_forward(self, folder_name, target_node, file_path, original_filename, sender_node):
        """Check if the target node and cloud nodes are available and forward the file."""
        cloud_node_ips = ["192.168.1.6", "192.168.1.7", "192.168.1.8"]
        cloud_nodes = []
        for ip in cloud_node_ips:
            for node_ip, info in self.network.ip_map.items():
                if node_ip == ip:
                    cloud_nodes.append(info["node_name"])
                    break
            else:
                self.logger.warning(f"Cloud node with IP {ip} not found in IP_MAP")
                continue

        with self.active_nodes_lock:
            # Forward to the original target node if specified and active
            if target_node and target_node in self.active_nodes:
                self.logger.info(f"Target node {target_node} is active, forwarding file {original_filename}")
                self.network.forward_file(folder_name, target_node)
            elif target_node:
                self.logger.warning(f"Target node {target_node} is not active, queuing file {original_filename}")

            # Forward to all active cloud nodes
            for cloud_node in cloud_nodes:
                if cloud_node in self.active_nodes:
                    self.logger.info(f"Cloud node {cloud_node} is active, forwarding file {original_filename} from {sender_node}")
                    cloud_folder_name = f"{folder_name}_cloud_{cloud_node}"
                    cloud_file_path = os.path.join(self.disk_path, cloud_folder_name, original_filename)
                    os.makedirs(os.path.dirname(cloud_file_path), exist_ok=True)
                    import shutil
                    shutil.copy2(file_path, cloud_file_path)
                    with self.pending_files_lock:
                        self.pending_files[cloud_folder_name] = (cloud_node, original_filename, sender_node)
                    self.network.forward_file(cloud_folder_name, cloud_node)
                else:
                    self.logger.warning(f"Cloud node {cloud_node} is not active, skipping file {original_filename}")