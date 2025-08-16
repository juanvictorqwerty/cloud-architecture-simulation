import os
import re
import tempfile
import shutil
from pyftpdlib.handlers import FTPHandler

class ServerFTPHandler(FTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_state = {
            "current_filename": None,
            "expected_chunks": 5,
            "received_chunks": 0,
            "total_received_size": 0,
            "target_node": None,
            "temp_file_path": None,
            "expected_chunk_size": None,
            "folder_name": None
        }

    def _get_unique_folder_name(self):
        """Generate a unique folder name (e.g., file_001)."""
        counter = 1
        while True:
            folder_name = f"file_{counter:03d}"
            folder_path = os.path.join(self.server.manager.disk_path, folder_name)
            with self.server.manager.pending_files_lock:
                if not os.path.exists(folder_path) and folder_name not in self.server.manager.pending_files:
                    return folder_name
            counter += 1

    def on_file_received(self, file_path):
        """Handle chunk reception for the server."""
        logger = self.server.manager.logger
        with open(file_path, 'rb') as f:
            data = f.read()

        # Server expects a 3-part header from a node
        header_pattern = re.compile(b"CHUNK:(\d+):(\d+):([^\n]+)\n")
        match = header_pattern.match(data)
        if not match:
            logger.error(f"Invalid chunk header in {file_path}")
            try:
                os.remove(file_path)
            except OSError:
                pass
            return

        chunk_number = int(match.group(1))
        chunk_size = int(match.group(2))
        target_node = match.group(3).decode()
        header_end = match.end()
        # Validate target_node
        if not any(node_info['node_name'] == target_node for node_info in self.server.manager.network.ip_map.values()):
            logger.error(f"Invalid target node '{target_node}' in header from {file_path}. Node does not exist.")
            try:
                os.remove(file_path)
            except OSError:
                pass
            return

        payload = data[header_end:header_end + chunk_size]
        actual_payload_size = len(payload)

        if actual_payload_size != chunk_size:
            logger.error(f"Chunk {chunk_number} size mismatch, expected {chunk_size}, got {actual_payload_size}")
            return

        original_filename = os.path.basename(file_path)

        if chunk_number == 1:
            folder_name = self._get_unique_folder_name()
            folder_path = os.path.join(self.server.manager.disk_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            self.session_state["current_filename"] = original_filename
            self.session_state["received_chunks"] = 1
            self.session_state["total_received_size"] = actual_payload_size
            self.session_state["target_node"] = target_node
            self.session_state["folder_name"] = folder_name
            self.session_state["temp_file_path"] = tempfile.NamedTemporaryFile(delete=False, dir=folder_path).name
            self.session_state["expected_chunk_size"] = chunk_size
            with open(self.session_state["temp_file_path"], 'wb') as f:
                f.write(payload)
            with self.server.manager.pending_files_lock:
                self.server.manager.pending_files[folder_name] = (target_node, original_filename)
        else:
            # Add validation for subsequent chunks
            if original_filename != self.session_state.get("current_filename") or target_node != self.session_state.get("target_node"):
                logger.error(f"Chunk {chunk_number} for {original_filename}:{target_node} does not match expected {self.session_state.get('current_filename')}:{self.session_state.get('target_node')}")
                return
            if chunk_number != self.session_state.get("received_chunks", 0) + 1:
                logger.error(f"Received chunk {chunk_number} out of order, expected {self.session_state.get('received_chunks', 0) + 1}")
                return
            
            self.session_state["received_chunks"] += 1
            self.session_state["total_received_size"] += actual_payload_size
            with open(self.session_state["temp_file_path"], 'ab') as f:
                f.write(payload)

        logger.info(f"Received chunk {chunk_number}/{self.session_state['expected_chunks']} for {original_filename} (folder: {self.session_state['folder_name']}, target: {target_node})")

        if self.session_state["received_chunks"] == self.session_state["expected_chunks"]:
            final_path = os.path.join(self.server.manager.disk_path, self.session_state["folder_name"], original_filename)
            os.rename(self.session_state["temp_file_path"], final_path)
            logger.info(f"Stored {original_filename} in folder {self.session_state['folder_name']} for {target_node}")
            
            self.server.manager.check_node_and_forward(self.session_state["folder_name"], target_node, final_path, original_filename)
            
            # Reset state
            self.session_state = {k: None for k in self.session_state}
            self.session_state["expected_chunks"] = 5

        try:
            os.remove(file_path)
        except OSError:
            pass