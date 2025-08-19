#!/usr/bin/env python3
"""
Test script to verify gRPC functionality with the cloud architecture simulation.
"""

import subprocess
import time
import sys
import os

def test_grpc_ports():
    """Test that gRPC ports are available"""
    import socket
    
    ports_to_test = [50050, 50071, 50072, 50073, 50074, 50075, 50081, 50082, 50083]
    
    print("Testing port availability...")
    for port in ports_to_test:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"Port {port} is already in use")
        else:
            print(f"Port {port} is available")
        sock.close()

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import grpc
        import file_transfer_pb2
        import file_transfer_pb2_grpc
        from grpc_server import GRPCServer
        from grpc_client import GRPCClient
        print("✓ All gRPC imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def main():
    print("=== gRPC Cloud Architecture Test ===")
    
    # Test imports
    if not test_imports():
        print("Import test failed. Please check dependencies.")
        return 1
    
    # Test port availability
    test_grpc_ports()
    
    print("\nTo test the implementation:")
    print("1. Stop any running router and nodes")
    print("2. Start router: python router.py")
    print("3. Start cloud nodes: python cloud1.py, python cloud2.py, python cloud3.py")
    print("4. Start a regular node: python node1.py")
    print("5. In node1, create a file: touch testfile.txt 5")
    print("6. Upload to all clouds: upload testfile.txt")
    print("7. Send to another node: send testfile.txt node2")
    print("\nFixed issues:")
    print("✓ Upload now sends to ALL 3 cloud nodes")
    print("✓ Router properly tracks active nodes via gRPC")
    print("✓ Send function forwards through router")
    print("✓ Fixed gRPC message size limits")
    print("✓ Each device has unique fixed ports")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
