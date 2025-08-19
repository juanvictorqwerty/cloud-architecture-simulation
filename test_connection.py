#!/usr/bin/env python3
"""
Test gRPC connections to different node types
"""

import time
import threading
from grpc_server import GRPCServer
from grpc_client import GRPCClient

def test_node_connection():
    """Test connection to a regular node"""
    print("Testing regular node connection...")
    
    # Start a regular node server
    server = GRPCServer("test_node", "./test_disk", 8091, is_router=False)
    
    def start_server():
        return server.start()
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)  # Wait for server to start
    
    # Test connection
    client = GRPCClient()
    success = client.connect(8091)
    
    if success:
        print("✓ Successfully connected to regular node")
        client.disconnect()
        server.stop()
        return True
    else:
        print("✗ Failed to connect to regular node")
        server.stop()
        return False

def test_router_connection():
    """Test connection to a router"""
    print("Testing router connection...")
    
    # Start a router server
    server = GRPCServer("test_router", "./test_disk", 8092, is_router=True)
    
    def start_server():
        return server.start()
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(1)  # Wait for server to start
    
    # Test connection
    client = GRPCClient()
    success = client.connect(8092)
    
    if success:
        print("✓ Successfully connected to router")
        client.disconnect()
        server.stop()
        return True
    else:
        print("✗ Failed to connect to router")
        server.stop()
        return False

def main():
    print("=== gRPC Connection Test ===")
    
    node_success = test_node_connection()
    print()
    router_success = test_router_connection()
    
    print("\nResults:")
    if node_success and router_success:
        print("✓ All connection tests passed!")
        print("The gRPC implementation should now work correctly.")
        return 0
    else:
        print("✗ Some connection tests failed.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
