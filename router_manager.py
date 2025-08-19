import threading
import socket
import logging
import json
from virtual_network import VirtualNetwork
from config import SERVER_IP, SERVER_SOCKET_PORT, SERVER_DISK_PATH, SERVER_GRPC_PORT
from grpc_server import GRPCServer

class RouterManager:
    def __init__(self):
        self.ip_address = SERVER_IP
        self.grpc_port = SERVER_GRPC_PORT
        self.disk_path = SERVER_DISK_PATH
        self.network = VirtualNetwork(self)
        self.pending_files = {}
        self.pending_files_lock = threading.Lock()
        self.grpc_server = None
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
        """Start the gRPC server and socket server."""
        # Start gRPC server
        self.grpc_server = GRPCServer("router", self.disk_path, self.grpc_port, is_router=True, router_manager=self)

        def start_grpc():
            result = self.grpc_server.start()
            if result is not None:
                self.logger.info(f"gRPC server successfully started on {self.ip_address}:{self.grpc_port}")
                print(f"✓ Router gRPC server started on port {self.grpc_port}")
            else:
                self.logger.error(f"gRPC server failed to start on {self.ip_address}:{self.grpc_port}")
                print(f"✗ Router gRPC server failed to start")

        grpc_thread = threading.Thread(target=start_grpc, daemon=True)
        grpc_thread.start()

        # Start socket server (for legacy compatibility)
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_server.bind(("0.0.0.0", self.socket_port))
        self.socket_server.listen(10)
        socket_thread = threading.Thread(target=self._handle_socket_connections, daemon=True)
        socket_thread.start()
        self.logger.info(f"Socket server started on {self.ip_address}:{self.socket_port}")
        print(f"✓ Router socket server started on port {self.socket_port}")

    def stop(self):
        """Stop the gRPC server and socket server."""
        if self.grpc_server:
            self.grpc_server.stop()
            self.logger.info(f"gRPC server stopped for {self.ip_address}")
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
            """Forward the file to the requested node *and* replicate to every cloud node."""
            from virtual_network import VirtualNetwork  # local import to avoid circularity
    
            # 1) Forward to the originally requested node (if on-line)
            with self.active_nodes_lock:
                if target_node in self.active_nodes:
                    self.logger.info(f"Target node {target_node} is active, forwarding {original_filename}")
                    self.network.forward_file(folder_name, target_node)
                else:
                    self.logger.warning(f"Target node {target_node} not active, transfer failed for {original_filename}")
    
            # 2) replicate to every cloud node
            for ip, info in self.network.ip_map.items():
                if info["node_name"].startswith("cloud") and info["node_name"] != target_node:
                    filename_to_send = original_filename   # keep original name
                    self.logger.info(f"Replicating {filename_to_send} to {info['node_name']}")
                    self.network.forward_file(folder_name,
                                            info["node_name"],
                                            is_replication=True,
                                            original_filename=filename_to_send)