import os
import re
import tempfile
import shutil
from pyftpdlib.handlers import FTPHandler

class NodeFTPHandler(FTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_state = {
            "current_filename": None,
            "expected_chunks": 5,
            "received_chunks": 0,
            "total_received_size": 0,
            "temp_file_path": None,
            "expected_chunk_size": None
        }

    def safe_rename(self, src, dst):
        """Rename src -> dst, deleting dst if it already exists."""
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)

    def on_file_received(self, file_path):
        """Handle chunk reception for nodes."""
        if file_path.endswith("disk_metadata.json"):
            return

        with open(file_path, 'rb') as f:
            data = f.read()

        # Node expects a 2-part header from the server
        header_pattern = re.compile(b"CHUNK:(\d+):(\d+)\n")
        match = header_pattern.match(data)
        if not match:
            print(f"Error: Invalid chunk header in {file_path}")
            try:
                os.remove(file_path)
            except OSError:
                pass
            return

        chunk_number = int(match.group(1))
        chunk_size = int(match.group(2))
        header_end = match.end()
        payload = data[header_end:header_end + chunk_size]
        actual_payload_size = len(payload)

        if actual_payload_size != chunk_size:
            print(f"Error: Chunk {chunk_number} size mismatch, expected {chunk_size}, got {actual_payload_size}")
            return

        filename = os.path.basename(file_path)
        
        if chunk_number == 1:
            self.session_state["current_filename"] = filename
            self.session_state["received_chunks"] = 1
            self.session_state["total_received_size"] = actual_payload_size
            self.session_state["temp_file_path"] = tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(file_path)).name
            self.session_state["expected_chunk_size"] = chunk_size
            with open(self.session_state["temp_file_path"], 'wb') as f:
                f.write(payload)
        else:
            # Validation for subsequent chunks
            if filename != self.session_state.get("current_filename"):
                print(f"Error: Chunk {chunk_number} for {filename} does not match expected file {self.session_state.get('current_filename')}")
                return
            if chunk_number != self.session_state.get("received_chunks", 0) + 1:
                print(f"Error: Received chunk {chunk_number} out of order, expected {self.session_state.get('received_chunks', 0) + 1}")
                return
            
            self.session_state["received_chunks"] += 1
            self.session_state["total_received_size"] += actual_payload_size
            with open(self.session_state["temp_file_path"], 'ab') as f:
                f.write(payload)

        print(f"Received chunk {chunk_number}/{self.session_state['expected_chunks']} for {filename}: {self.session_state['total_received_size']} bytes total")

        if self.session_state["received_chunks"] == self.session_state["expected_chunks"]:
            final_path = os.path.join(os.path.dirname(file_path), self.session_state["current_filename"])
            self.safe_rename(self.session_state["temp_file_path"], final_path)
            
            # Update the node's virtual disk
            final_size = os.path.getsize(final_path)
            self.server.node.virtual_disk[self.session_state["current_filename"]] = final_size
            self.server.node._save_disk()
            print(f"Completed receiving {self.session_state['current_filename']}: {final_size} bytes")
            
            # Reset state for the next transfer
            self.session_state = {k: None for k in self.session_state}
            self.session_state["expected_chunks"] = 5

        # If you intended to remove a file, complete the statement and handle exceptions
        # Example: try to remove the original chunk file after processing
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"Warning: Failed to remove {file_path}: {e}")