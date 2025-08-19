#!/usr/bin/env python3
"""
Port checker script to diagnose gRPC port conflicts
"""

import socket
import subprocess
import sys

def check_port(host, port):
    """Check if a port is in use"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def get_port_info(port):
    """Get information about what's using a port (Windows)"""
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        for line in lines:
            if f':{port}' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    return f"PID {pid}"
    except:
        pass
    return "Unknown"

def main():
    print("=== gRPC Port Status Check ===")
    
    # Define all ports used in the system
    ports = {
        8000: "Router gRPC",
        8001: "Node1 gRPC",
        8002: "Node2 gRPC",
        8003: "Node3 gRPC",
        8004: "Node4 gRPC",
        8005: "Node5 gRPC",
        8011: "Cloud1 gRPC",
        8012: "Cloud2 gRPC",
        8013: "Cloud3 gRPC",
        2120: "Router FTP",
        2121: "Node1 FTP",
        2122: "Node2 FTP",
        2123: "Node3 FTP",
        2124: "Node4 FTP",
        2125: "Node5 FTP",
        2131: "Cloud1 FTP",
        2132: "Cloud2 FTP",
        2133: "Cloud3 FTP",
        9999: "Router Socket"
    }
    
    print(f"{'Port':<6} {'Service':<15} {'Status':<10} {'Process'}")
    print("-" * 50)
    
    for port, service in ports.items():
        in_use = check_port('127.0.0.1', port)
        status = "IN USE" if in_use else "FREE"
        process_info = get_port_info(port) if in_use else ""
        print(f"{port:<6} {service:<15} {status:<10} {process_info}")
    
    print("\nRecommendations:")
    print("1. Stop all running nodes and router")
    print("2. Check for any stuck processes using the ports")
    print("3. Restart router first, then nodes one by one")
    print("4. If ports are still in use, restart your terminal/IDE")

if __name__ == "__main__":
    main()
