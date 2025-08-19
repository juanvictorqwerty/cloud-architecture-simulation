import os
import json
import threading
from virtual_network import VirtualNetwork
from config import IP_MAP, SERVER_GRPC_PORT
from grpc_server import GRPCServer
from grpc_client import GRPCClient

class VirtualNode:
    def __init__(self, name, disk_path, ip_address):
        self.name = name
        self.disk_path = disk_path
        self.ip_address = ip_address
        self.grpc_port = IP_MAP[ip_address]["grpc_port"]
        self.virtual_disk = {}
        self.memory = {}
        self.is_running = False
        self.ip_map = IP_MAP
        self.network = VirtualNetwork()
        self.grpc_server = None
        self.grpc_client = GRPCClient()
        self._initialize_disk()
        # Start gRPC server only
        self._start_grpc_server()
        self.start()

    def _initialize_disk(self):
        os.makedirs(self.disk_path, exist_ok=True)
        metadata_path = os.path.join(self.disk_path, "disk_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.virtual_disk = json.load(f)
                    self.virtual_disk = {k: int(v) for k, v in self.virtual_disk.items()}
            except (json.JSONDecodeError, IOError):
                print(f"Warning: Could not load metadata from {metadata_path}. Starting with empty disk.")
                self.virtual_disk = {}
        else:
            self.virtual_disk = {}
            self._save_disk()
        for filename in os.listdir(self.disk_path):
            if filename != "disk_metadata.json":
                file_path = os.path.join(self.disk_path, filename)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    self.virtual_disk[filename] = size
        self._save_disk()

    def _save_disk(self):
        metadata_path = os.path.join(self.disk_path, "disk_metadata.json")
        try:
            with open(metadata_path, 'w') as f:
                json.dump(self.virtual_disk, f)
        except IOError as e:
            print(f"Error saving metadata to {metadata_path}: {e}")

    def _start_grpc_server(self):
        """Start the gRPC server for this node"""
        try:
            # Nodes are not routers, so is_router=False (default)
            self.grpc_server = GRPCServer(self.name, self.disk_path, self.grpc_port, is_router=False)

            # Start server in a separate thread
            def start_server():
                result = self.grpc_server.start()
                if result is None:
                    print(f"gRPC server failed to start for {self.name}")
                    self.grpc_server = None
                else:
                    print(f"gRPC server successfully started for {self.name}")

            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()

        except Exception as e:
            print(f"Exception starting gRPC server for {self.name}: {e}")
            self.grpc_server = None

    def send(self, filename, target_node_name):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"

        if not any(node_info['node_name'] == target_node_name for node_info in self.ip_map.values()):
            return f"Error: Target node '{target_node_name}' does not exist."

        if filename not in self.virtual_disk:
            return f"Error: File {filename} not found locally"

        # Check if transfer is allowed based on links
        from links_manager import LinksManager
        lm = LinksManager()

        if not lm.is_transfer_allowed(self.name, target_node_name):
            return f"Error: Transfer denied. Nodes {self.name} and {target_node_name} are not in the same link."

        # Use gRPC to send file via router
        file_path = os.path.join(self.disk_path, filename)

        try:
            result = self.grpc_client.send_file(
                file_path=file_path,
                filename=filename,
                target_node=target_node_name,
                sender_node=self.name,
                port=SERVER_GRPC_PORT
            )
            return result
        except Exception as e:
            return f"Error sending file via gRPC: {e}"
    
    # ----------  UPLOAD ----------
    def upload(self, filename):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        if filename not in self.virtual_disk:
            return f"Error: File {filename} not found locally"

        cloud_nodes = ["cloud1", "cloud2", "cloud3"]
        file_path = os.path.join(self.disk_path, filename)

        # Upload to ALL cloud nodes for redundancy
        successful_uploads = []
        failed_uploads = []

        for target_cloud in cloud_nodes:
            try:
                # Use gRPC to upload to cloud node via router
                result = self.grpc_client.send_file(
                    file_path=file_path,
                    filename=filename,
                    target_node=target_cloud,
                    sender_node=self.name,
                    port=SERVER_GRPC_PORT
                )

                if "Error" not in result:
                    successful_uploads.append(target_cloud)
                    print(f"✓ Successfully uploaded {filename} to {target_cloud}")
                else:
                    failed_uploads.append(target_cloud)
                    print(f"✗ Failed to upload {filename} to {target_cloud}: {result}")

            except Exception as e:
                failed_uploads.append(target_cloud)
                print(f"✗ Exception uploading to {target_cloud}: {e}")

        if successful_uploads:
            return f"File {filename} uploaded to {len(successful_uploads)}/3 cloud nodes: {', '.join(successful_uploads)}"
        else:
            return "Error: Failed to upload file to any cloud node."

    # ----------  DOWNLOAD ----------
    def download(self, filename):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"

        from links_manager import LinksManager   # local import to avoid circular
        lm = LinksManager()

        # discover which cloud node owns the file
        owner = None
        for cloud in ["cloud1", "cloud2", "cloud3"]:
            if filename in VirtualNode._peek_virtual_disk(cloud):
                owner = cloud
                break
        if not owner:
            return f"Error: {filename} not found in any cloud node"

        # link check
        # Cloud nodes bypass link checks for downloads
        # if not any({self.name, owner} <= set(nodes) for nodes in lm.links.values()):
        #     return f"Error: {self.name} and {owner} are not in the same link – download denied"

        # Download the file from the cloud node via router
        owner_grpc_port = next(info["grpc_port"] for info in IP_MAP.values() if info["node_name"] == owner)

        # First check if file exists on the cloud node
        file_info = self.grpc_client.get_file_info(filename, owner_grpc_port)
        if not file_info or not file_info['exists']:
            return f"Error: {filename} not found on {owner}"

        print(f"Requesting download of {filename} from {owner}...")

        # Request the cloud node to send the file to us via the router using gRPC
        try:
            # Use the existing send mechanism but from cloud to this node
            owner_ip = next(ip for ip, info in IP_MAP.items() if info["node_name"] == owner)

            # Request router to coordinate transfer from cloud to this node via gRPC
            result = self.network.send_file_grpc(filename, owner_ip, VirtualNode._peek_virtual_disk(owner), self.name)

            if "Error" not in result:
                # Wait a moment for file transfer to complete
                import time
                time.sleep(2)

                # Refresh disk and check if file was received
                self._refresh_disk()
                local_file_path = os.path.join(self.disk_path, filename)
                if os.path.exists(local_file_path):
                    file_size = os.path.getsize(local_file_path)
                    self.virtual_disk[filename] = file_size
                    self._save_disk()
                    return f"Downloaded {filename} from {owner} ({file_size} bytes)"
                else:
                    return f"Transfer initiated but file not yet received. Try 'ls' in a moment."
            else:
                return f"Error downloading {filename}: {result}"

        except Exception as e:
            return f"Error downloading {filename}: {e}"

    # ----------  helper ----------
    @staticmethod
    def _peek_virtual_disk(node_name):
        """return the virtual_disk dict of a cloud node without instantiating it"""
        disk_path = next(info["disk_path"] for info in IP_MAP.values() if info["node_name"] == node_name)
        meta = os.path.join(disk_path, "disk_metadata.json")
        if not os.path.exists(meta):
            return {}
        try:
            with open(meta) as f:
                return {k: int(v) for k, v in json.load(f).items() if not k.endswith(".metadata")}
        except Exception:
            return {}

    def start(self):
        if self.is_running:
            return f"VM {self.name} is already running"
        self.is_running = True

        # Register with router via gRPC
        try:
            success = self.grpc_client.register_node(
                node_name=self.name,
                ip_address=self.ip_address,
                port=self.grpc_port,
                router_port=SERVER_GRPC_PORT
            )
            if success:
                print(f"VM {self.name} registered with router via gRPC")
            else:
                print(f"Failed to register {self.name} with router via gRPC")
        except Exception as e:
            print(f"gRPC registration failed: {e}")

        print(f"VM {self.name} started")
        return f"VM {self.name} started"

    def stop(self):
        if not self.is_running:
            return f"VM {self.name} is already stopped"
        self.is_running = False

        # Unregister from router via gRPC
        try:
            self.grpc_client.unregister_node(
                node_name=self.name,
                ip_address=self.ip_address,
                port=self.grpc_port,
                router_port=SERVER_GRPC_PORT
            )
        except Exception as e:
            print(f"Error unregistering from router: {e}")

        # Stop gRPC server
        if self.grpc_server:
            self.grpc_server.stop()

        print(f"VM {self.name} stopped")
        return f"VM {self.name} stopped"

    def _refresh_disk(self):
        # Clear existing virtual disk entries, but keep metadata if it exists
        self.virtual_disk = {k: v for k, v in self.virtual_disk.items() if k == "disk_metadata.json"}
        for filename in os.listdir(self.disk_path):
            if filename != "disk_metadata.json":
                file_path = os.path.join(self.disk_path, filename)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    self.virtual_disk[filename] = size
        self._save_disk()

    def ls(self):
        self._refresh_disk()
        files = [f"{k} ({v} bytes)" for k, v in self.virtual_disk.items() if k != "disk_metadata.json"]
        if not files:
            return "No files found"
        return "\n".join(files)

    def touch(self, filename, size=0):
        if filename in self.virtual_disk:
            return f"Error: File {filename} already exists"
        file_path = os.path.join(self.disk_path, filename)
        try:
            # Convert MB to bytes (1 MB = 1,048,576 bytes)
            size_bytes = size * 1024 * 1024
            with open(file_path, 'wb') as f:
                if size_bytes > 0:
                    f.write(b'\0' * size_bytes)
            self.virtual_disk[filename] = size_bytes
            self._save_disk()
            return f"Created {filename} with size {size} MB"
        except Exception as e:
            return f"Error creating file {filename}: {e}"

    def trunc(self, filename, size):
        if filename not in self.virtual_disk:
            return f"Error: File {filename} not found"
        file_path = os.path.join(self.disk_path, filename)
        try:
            # Convert MB to bytes (1 MB = 1,048,576 bytes)
            size_bytes = size * 1024 * 1024
            with open(file_path, 'wb') as f:
                f.write(b'\0' * size_bytes)
            self.virtual_disk[filename] = size_bytes
            self._save_disk()
            return f"Truncated {filename} to {size} MB"
        except Exception as e:
            return f"Error truncating file {filename}: {e}"

    def del_file(self, filename):
        if filename == "all":
            for fname in list(self.virtual_disk.keys()):
                if fname != "disk_metadata.json":
                    try:
                        os.remove(os.path.join(self.disk_path, fname))
                        del self.virtual_disk[fname]
                    except Exception as e:
                        print(f"Error deleting {fname}: {e}")
            self._save_disk()
            return "Deleted all files"
        if filename not in self.virtual_disk:
            return f"Error: File {filename} not found"
        try:
            os.remove(os.path.join(self.disk_path, filename))
            del self.virtual_disk[filename]
            self._save_disk()
            return f"Deleted {filename}"
        except Exception as e:
            return f"Error deleting {filename}: {e}"

    def diskprop(self):
        used = sum(self.virtual_disk.values())
        return f"Disk: {used} bytes used"

    def set_var(self, var_name, value):
        try:
            self.memory[var_name] = int(value)
            return f"Set {var_name} = {value}"
        except ValueError:
            return f"Error: {value} is not a valid integer"

    def get_var(self, var_name):
        if var_name in self.memory:
            return f"{var_name} = {self.memory[var_name]}"
        return f"Error: Variable {var_name} not found in memory"

    def _is_cloud_node(self, name):
        return name.startswith("cloud")

    def _in_same_link(self, target):
        """Check if `self.name` and `target` appear in the same link."""
        import links_manager  # local import
        lm = links_manager.LinksManager()
        for members in lm.links.values():
            if self.name in members and target in members:
                return True
        return False

    def get(self, filename, source_node_name):
        """
        Simulate a download:
        - If source is a cloud node we allow it regardless of links.
        - Otherwise the two nodes must share a link.
        """
        if not self.is_running:
            return f"Error: VM {self.name} is not running"

        if source_node_name == self.name:
            return "Error: Cannot get a file from yourself"

        # Does the source node exist?
        src_ip = None
        for ip, info in self.ip_map.items():
            if info["node_name"] == source_node_name:
                src_ip = ip
                break
        if not src_ip:
            return f"Error: Source node {source_node_name} does not exist"

        # Cloud nodes bypass link checks
        if not self._is_cloud_node(source_node_name) and not self._in_same_link(source_node_name):
            return f"Error: Node {self.name} and {source_node_name} are not in the same link"

        # Pull from source
        try:
            result = self.network.send_file(filename, src_ip, self.network.ip_map[src_ip]["disk_path"], self.name)
            return result.replace("sent", "downloaded")
        except Exception as e:
            return f"Error downloading {filename}: {e}"

    def execute_instruction(self, instruction):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        parts = instruction.strip().split()
        if not parts:
            return "No instruction provided"
        cmd = parts[0].lower()
        if cmd == "add":
            if len(parts) == 3:
                var1, var2 = parts[1], parts[2]
                if var1 in self.memory and var2 in self.memory:
                    result = self.memory[var1] + self.memory[var2]
                    self.memory["result"] = result
                    return f"Added {var1} + {var2}, stored result = {result}"
                return "Error: Variables not found"
            return "Error: Usage: add <var1> <var2>"
        return "Unknown instruction"

    def __str__(self):
        status = "running" if self.is_running else "stopped"
        return f"VirtualNode({self.name}, IP: {self.ip_address}, Status: {status}, Files: {len(self.virtual_disk)}, Memory: {len(self.memory)} variables)"

    def run_interactive(self):
        print(self)
        while self.is_running:
            try:
                command = input(f"{self.name}>> ").strip().split()
                if not command:
                    continue
                cmd = command[0].lower()
                if cmd == "ls":
                    print(self.ls())
                elif cmd == "touch" and len(command) > 1:
                    size = int(command[2]) if len(command) > 2 and command[2].isdigit() else 0
                    print(self.touch(command[1], size))
                elif cmd == "trunc" and len(command) > 1:
                    size = int(command[2]) if len(command) > 2 and command[2].isdigit() else 0
                    print(self.trunc(command[1], size))
                elif cmd == "send" and len(command) == 3:
                    print(self.send(command[1], command[2]))
                elif cmd == "del" and len(command) == 2:
                    print(self.del_file(command[1]))
                elif cmd == "diskprop" and len(command) == 1:
                    print(self.diskprop())
                elif cmd == "set" and len(command) == 3:
                    print(self.set_var(command[1], command[2]))
                elif cmd == "get" and len(command) == 2:
                    print(self.get_var(command[1]))
                elif cmd == "add" and len(command) == 3:
                    print(self.execute_instruction(" ".join(command)))
                elif cmd == "get" and len(command) == 3:
                    print(self.get(command[1], command[2]))
                elif cmd == "upload" and len(command) == 2:
                    print(self.upload(command[1]))
                elif cmd == "download" and len(command) == 2:
                    print(self.download(command[1]))
                elif cmd == "stop":
                    print(self.stop())
                    break
                else:
                    print("Invalid command. Use: Valid commands: ls, touch <file> [size], trunc <file> [size],send <file> <node>, upload <file>, download <file>, del <file|all>, diskprop, stop")
            except EOFError:
                print("\nEOF detected. Stopping VM.")
                print(self.stop())
                break
            except KeyboardInterrupt:
                print("\nKeyboard interrupt detected. Stopping VM.")
                print(self.stop())
                break
            except Exception as e:
                print(f"Error processing command: {e}")