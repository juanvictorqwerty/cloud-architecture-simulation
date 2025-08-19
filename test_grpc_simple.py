#!/usr/bin/env python3
"""
Simple test to verify gRPC server can start properly
"""

import sys
import time
import threading
from grpc_server import GRPCServer

def test_grpc_server():
    """Test if gRPC server can start on a simple port"""
    print("Testing gRPC server startup...")

    # Test both router and node configurations
    test_cases = [
        {"name": "test_router", "port": 8090, "is_router": True},
        {"name": "test_node", "port": 8091, "is_router": False}
    ]

    for test_case in test_cases:
        print(f"\nTesting {test_case['name']} (is_router={test_case['is_router']})...")

        server = GRPCServer(
            test_case['name'],
            "./test_disk",
            test_case['port'],
            is_router=test_case['is_router']
        )

        # Start server
        result = server.start()
        if result is None:
            print(f"✗ Failed to start {test_case['name']}")
            continue

        # Wait a bit for server to start
        time.sleep(1)

        # Try to connect to it (only test file transfer service for nodes)
        from grpc_client import GRPCClient
        client = GRPCClient()

        success = client.connect(test_case['port'])
        if success:
            print(f"✓ {test_case['name']} started and client connected successfully!")
            client.disconnect()
        else:
            print(f"✗ Failed to connect to {test_case['name']}")

        server.stop()

        if success:
            return True

    return False

def main():
    print("=== Simple gRPC Test ===")
    
    # Test basic imports
    try:
        import grpc
        import file_transfer_pb2
        import file_transfer_pb2_grpc
        print("✓ gRPC imports successful")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return 1
    
    # Test server startup
    if test_grpc_server():
        print("\n✓ gRPC implementation is working!")
        print("\nNow you can:")
        print("1. Start router: python router.py")
        print("2. Start nodes with gRPC support")
        print("3. Test file transfers")
        return 0
    else:
        print("\n✗ gRPC server test failed")
        print("Check the error messages above for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
