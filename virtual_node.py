import os
import json
import socket
from virtual_network import VirtualNetwork
import threading
from config import IP_MAP, SERVER_IP, SERVER_SOCKET_PORT
import file_store

class VirtualNode:
    def __init__(self, name, disk_path, ip_address, ftp_port):
        self.name = name
        self.disk_path = disk_path
        self.ip_address = ip_address
        self.ftp_port = ftp_port
        self.virtual_disk = {}
        self.memory = {}
        self.is_running = False
        self.ip_map = IP_MAP
        self.network = VirtualNetwork()
        self._initialize_disk()
        self.network.start_ftp_server(self, ip_address, ftp_port, disk_path)
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

    def send(self, filename, target_node_name):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        
        if not any(node_info['node_name'] == target_node_name for node_info in self.ip_map.values()):
            return f"Error: Target node '{target_node_name}' does not exist."

        target_ip = self.network.server_ip
        result = [None]  # Use a list to store result, as nonlocal variables in inner functions need mutable objects
        def send_task():
            try:
                result[0] = self.network.send_file(filename, self.ip_address, self.virtual_disk, target_node_name)
            except Exception as e:
                result[0] = f"Error in send_file thread: {e}"
        
        thread = threading.Thread(target=send_task)
        thread.start()
        thread.join()  # Wait for the thread to complete to get the result
        return result[0] if result[0] else f"Attempting to send {filename} to {target_node_name} in the background."
    
        # ----------  UPLOAD ----------
    def upload(self, filename):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        if filename not in self.virtual_disk:
            return f"Error: File {filename} not found locally"

        cloud_nodes = ["cloud1", "cloud2", "cloud3"]
        
        # Attempt to upload to each cloud node until successful
        for target_cloud in cloud_nodes:
            try:
                # The send_file method will check if the target node is active
                # and handle the transfer. If the target node is not active,
                # the router will log a warning and the transfer will fail for that specific cloud node.
                # We don't need to explicitly check active_nodes here, as the router handles it. The router will also ensure the file keeps its original name.
                result = self.network.send_file(filename, self.ip_address, self.virtual_disk, target_cloud)
                if "Error" not in result: # If the transfer was successful to this cloud node
                    return result.replace("router", f"cloud storage ({target_cloud})")
            except Exception as e:
                print(f"Attempt to upload to {target_cloud} failed: {e}")
        return "Error: Failed to upload file to any active cloud node."

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

        # trigger router-mediated transfer
        result = self.network.send_file(filename,
                                        next(ip for ip, info in IP_MAP.items() if info["node_name"] == owner),
                                        VirtualNode._peek_virtual_disk(owner),
                                        self.name)
        return result

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
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER_IP, SERVER_SOCKET_PORT))
            message = json.dumps({"action": "node_started", "node_name": self.name})
            sock.send(message.encode())
            sock.close()
            print(f"VM {self.name} started")
        except Exception as e:
            print(f"Error notifying router of start: {e}")
        return f"VM {self.name} started"

    def stop(self):
        if not self.is_running:
            return f"VM {self.name} is already stopped"
        self.is_running = False
        self.network.stop_ftp_server(self.ip_address)
        print(f"VM {self.name} stopped")
        return f"VM {self.name} stopped"

    def ls(self):
        return "\n".join([f"{k} ({v} bytes)" for k, v in self.virtual_disk.items() if k != "disk_metadata.json"])

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