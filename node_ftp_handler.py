import os
import re
import tempfile
import json
from pyftpdlib.handlers import FTPHandler
from config import IP_MAP

class NodeFTPHandler(FTPHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_state = {
            "current_filename": None,
            "expected_chunks": None,
            "received_chunks": 0,
            "total_received_size": 0,
            "sender_node": None,
            "temp_file_path": None,
            "expected_chunk_size": None
        }

    def _get_unique_filename(self, filename):
        """Generate a unique filename for the node, checking virtual_disk."""
        node = self.server.node
        file_list = list(node.virtual_disk.keys())
        base, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename
        while new_filename in file_list or os.path.exists(os.path.join(node.disk_path, new_filename)):
            new_filename = f"{base}_{counter}{ext}"
            counter += 1
        return new_filename

    def on_file_received(self, file_path):
        """Handle chunk reception for the node."""
        node = self.server.node
        logger = self.server.manager.logger if hasattr(self.server, 'manager') else None
        with open(file_path, 'rb') as f:
            data = f.read()

        # Node expects a 5-part header: CHUNK:chunk_number:chunk_size:num_chunks:target_node:sender_node
        header_pattern = re.compile(b"CHUNK:(\d+):(\d+):(\d+):([^\n:]*):([^\n]*)\n")
        match = header_pattern.match(data)
        if not match:
            if logger:
                logger.error(f"Invalid chunk header in {file_path}")
            try:
                os.remove(file_path)
            except OSError:
                pass
            self.respond("550 Invalid chunk header")
            return

        chunk_number = int(match.group(1))
        chunk_size = int(match.group(2))
        num_chunks = int(match.group(3))
        target_node = match.group(4).decode()
        sender_node = match.group(5).decode()
        header_end = match.end()

        # Validate sender_node
        if not any(node_info['node_name'] == sender_node for node_info in IP_MAP.values()):
            if logger:
                logger.error(f"Invalid sender node '{sender_node}' in header from {file_path}")
            try:
                os.remove(file_path)
            except OSError:
                pass
            self.respond(f"550 Error: Sender node {sender_node} does not exist")
            return

        payload = data[header_end:header_end + chunk_size]
        actual_payload_size = len(payload)

        if actual_payload_size != chunk_size:
            if logger:
                logger.error(f"Chunk {chunk_number} size mismatch, expected {chunk_size}, got {actual_payload_size}")
            self.respond("550 Chunk size mismatch")
            return

        original_filename = self.current_name # Get the original filename from the FTP command argument

        # If this is a metadata file, handle it directly
        if original_filename.endswith(".metadata"):
            final_path = os.path.join(node.disk_path, original_filename)
            try:
                # If it's the first chunk (and should be the only chunk for metadata)
                if chunk_number == 1:
                    if os.path.exists(final_path):
                        os.remove(final_path) # Remove existing metadata file
                    with open(final_path, 'wb') as f:
                        f.write(payload) # Write the payload directly
                else:
                    # This case should ideally not happen for metadata files if sent as single chunks
                    # For now, just append, but this might indicate an issue if metadata is chunked
                    with open(final_path, 'ab') as f:
                        f.write(payload)

            except OSError as e:
                if logger:
                    logger.error(f"Error writing metadata file to {final_path}: {e}")
                self.respond(f"550 Error writing metadata file: {e}")
                return

            node.virtual_disk[original_filename] = os.path.getsize(final_path)
            node._save_disk()
            if logger:
                logger.info(f"Stored metadata file {original_filename} from {sender_node} in {node.disk_path}")
            self.respond(f"226 Transfer complete: {original_filename} stored from {sender_node}")
            
            # Clean up the temporary chunk file
            try:
                os.remove(file_path)
            except OSError:
                pass
            return # Exit, as metadata file is handled

        if chunk_number == 1:
            # Use the original filename
            unique_filename = original_filename
            self.session_state["current_filename"] = unique_filename
            self.session_state["expected_chunks"] = num_chunks
            self.session_state["received_chunks"] = 1
            self.session_state["total_received_size"] = actual_payload_size
            self.session_state["sender_node"] = sender_node
            self.session_state["temp_file_path"] = tempfile.NamedTemporaryFile(delete=False, dir=node.disk_path).name
            self.session_state["expected_chunk_size"] = chunk_size
            with open(self.session_state["temp_file_path"], 'wb') as f:
                f.write(payload)
        else:
            if original_filename != self.session_state.get("current_filename") or \
               sender_node != self.session_state.get("sender_node"):
                if logger:
                    logger.error(f"Chunk {chunk_number} for {original_filename}:{sender_node} does not match expected {self.session_state.get('current_filename')}:{self.session_state.get('sender_node')}")
                self.respond("550 Chunk mismatch")
                return
            if chunk_number != self.session_state.get("received_chunks", 0) + 1:
                if logger:
                    logger.error(f"Received chunk {chunk_number} out of order, expected {self.session_state.get('received_chunks', 0) + 1}")
                self.respond("550 Chunk out of order")
                return
            
            self.session_state["received_chunks"] += 1
            self.session_state["total_received_size"] += actual_payload_size
            with open(self.session_state["temp_file_path"], 'ab') as f:
                f.write(payload)

        if logger:
            logger.info(f"Received chunk {chunk_number}/{self.session_state['expected_chunks']} for {original_filename} (sender: {sender_node})")

        if self.session_state["received_chunks"] == self.session_state["expected_chunks"]:
            final_path = os.path.join(node.disk_path, self.session_state["current_filename"])
            try:
                if os.path.exists(final_path):
                    os.remove(final_path)
                os.rename(self.session_state["temp_file_path"], final_path)
            except OSError as e:
                if logger:
                    logger.error(f"Error renaming file to {final_path}: {e}")
                self.respond(f"550 Error renaming file: {e}")
                return

            node.virtual_disk[self.session_state["current_filename"]] = self.session_state["total_received_size"]
            node._save_disk()
            
            # Store sender information in a metadata file
            metadata_path = os.path.join(node.disk_path, f"{self.session_state['current_filename']}.metadata")
            metadata = {
                "sender_node": sender_node,
                "filename": self.session_state["current_filename"],
                "size": self.session_state["total_received_size"]
            }
            try:
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
                node.virtual_disk[f"{self.session_state['current_filename']}.metadata"] = os.path.getsize(metadata_path)
                node._save_disk()
            except IOError as e:
                if logger:
                    logger.error(f"Error saving metadata for {self.session_state['current_filename']}: {e}")
            
            if logger:
                logger.info(f"Stored {self.session_state['current_filename']} from {sender_node} in {node.disk_path}")
            self.respond(f"226 Transfer complete: {self.session_state['current_filename']} stored from {sender_node}")
            
            # Reset state
            self.session_state = {k: None for k in self.session_state}
            self.session_state["expected_chunks"] = None

        try:
            os.remove(file_path)
        except OSError:
            pass