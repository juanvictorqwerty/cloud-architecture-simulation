import os
from server_manager import FTPServerManager
from config import SERVER_DISK_PATH

if __name__ == "__main__":
    server_disk_path = SERVER_DISK_PATH
    os.makedirs(server_disk_path, exist_ok=True)
    server = FTPServerManager()
    server.start()
    print("Server running. Press Ctrl+C to stop.")
    try:
        while True:
            pass  # Keep server running
    except KeyboardInterrupt:
        server.stop()
        print("Server stopped.")