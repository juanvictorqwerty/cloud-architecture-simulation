import os
import json
import socket
from virtual_network import VirtualNetwork
import threading
from config import  IP_MAP , SERVER_IP, SERVER_SOCKET_PORT

class VirtualNode:
    def __init__(self, name, disk_path, ip_address, ftp_port):
        self.name = name
        self.disk_path = disk_path
        self.ip_address = ip_address
        self.ftp_port = ftp_port
        self.total_storage = 1024 * 1024 * 1024
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

    def _check_storage(self, size):
        used_storage = sum(self.virtual_disk.values())
        return used_storage + size <= self.total_storage

    def send(self, filename, target_node_name):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        
        if not any(node_info['node_name'] == target_node_name for node_info in self.ip_map.values()):
            return f"Error: Target node '{target_node_name}' does not exist."

        target_ip = self.network.server_ip
        def send_task():
            try:
                result = self.network.send_file(filename, self.ip_address, target_ip, self.virtual_disk, target_node_name)
                print(f"Send result: {result}")
            except Exception as e:
                print(f"Error in send_file thread: {e}")
        threading.Thread(target=send_task, args=()).start()
        return f"Attempting to send {filename} to {target_node_name} in the background."

    def start(self):
        if self.is_running:
            return f"VM {self.name} is already running"
        self.is_running = True
        # Notify server via socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER_IP, SERVER_SOCKET_PORT))
            message = json.dumps({"action": "node_started", "node_name": self.name})
            sock.send(message.encode())
            sock.close()
            print(f"Notified server of {self.name} startup")
        except Exception as e:
            print(f"Error notifying server: {e}")
        return f"VM {self.name} started"

    def stop(self):
        if not self.is_running:
            return f"VM {self.name} is already stopped"
        self.is_running = False
        self._save_disk()
        self.network.stop_ftp_server(self.ip_address)
        return f"VM {self.name} stopped"

    def ls(self):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        if not self.virtual_disk:
            return "Directory is empty"
        return "\n".join(f"{name}: {size} bytes" for name, size in self.virtual_disk.items())

    def touch(self, filename, size=0):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        try:
            size = int(size)
            if size < 0:
                return "Error: Size cannot be negative"
        except ValueError:
            return "Error: Size must be an integer"
        size_bytes = size * 1024 * 1024
        if filename not in self.virtual_disk:
            if not self._check_storage(size_bytes):
                return f"Error: Not enough storage on disk"
            file_path = os.path.join(self.disk_path, filename)
            with open(file_path, 'wb') as f:
                f.write(b"\0" * size_bytes)
            self.virtual_disk[filename] = size_bytes
            self._save_disk()
            return f"Created file: {filename} with {size_bytes} bytes ({size} MB)"
        else:
            os.utime(os.path.join(self.disk_path, filename))
            return f"Updated timestamp for file: {filename}"

    def trunc(self, filename, size=0):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        try:
            size = int(size)
            if size < 0:
                return "Error: Size cannot be negative"
        except ValueError:
            return "Error: Size must be an integer"
        size_bytes = size * 1024 * 1024
        if filename in self.virtual_disk:
            if not self._check_storage(size_bytes - self.virtual_disk[filename]):
                return f"Error: Not enough storage on disk"
            file_path = os.path.join(self.disk_path, filename)
            with open(file_path, 'wb') as f:
                f.write(b"\0" * size_bytes)
            self.virtual_disk[filename] = size_bytes
            self._save_disk()
            return f"Truncated {filename} to {size_bytes} bytes ({size} MB)"
        else:
            return f"File {filename} does not exist"

    def del_file(self, filename):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        if filename == "all":
            deleted_files = []
            for fname in list(self.virtual_disk.keys()):
                file_path = os.path.join(self.disk_path, fname)
                try:
                    os.remove(file_path)
                    deleted_files.append(fname)
                except OSError as e:
                    print(f"Error deleting {fname}: {e}")
            for fname in deleted_files:
                del self.virtual_disk[fname]
            self._save_disk()
            return f"Deleted {len(deleted_files)} file(s)" if deleted_files else "No files to delete"
        else:
            if filename not in self.virtual_disk:
                return f"Error: File {filename} does not exist"
            file_path = os.path.join(self.disk_path, filename)
            try:
                os.remove(file_path)
                del self.virtual_disk[filename]
                self._save_disk()
                return f"Deleted {filename}"
            except OSError as e:
                return f"Error deleting {filename}: {e}"

    def diskprop(self):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        total_size_bytes = self.total_storage
        occupied_size_bytes = sum(self.virtual_disk.values())
        free_size_bytes = total_size_bytes - occupied_size_bytes
        total_size_gb = total_size_bytes / (1024 * 1024 * 1024)
        occupied_size_mb = occupied_size_bytes / (1024 * 1024)
        free_size_mb = free_size_bytes / (1024 * 1024)
        return (f"Disk Properties for {self.name}:\n"
                f"Total Size: {total_size_gb:.2f} GB\n"
                f"Occupied Space: {occupied_size_mb:.2f} MB\n"
                f"Free Space: {free_size_mb:.2f} MB")

    def set_var(self, var_name, value):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        try:
            self.memory[var_name] = int(value)
            return f"Set {var_name} = {value} in memory as an integer"
        except ValueError:
            return f"Error: Value must be an integer"

    def get_var(self, var_name):
        if not self.is_running:
            return f"Error: VM {self.name} is not running"
        if var_name in self.memory:
            return f"{var_name} = {self.memory[var_name]}"
        else:
            return f"Variable {var_name} not found in memory"

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
                elif cmd == "stop":
                    print(self.stop())
                    break
                else:
                    print("Invalid command. Use: ls, touch <filename> [size], trunc <filename> [size], send <filename> <node_name>, del <filename|all>, diskprop, stop")
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