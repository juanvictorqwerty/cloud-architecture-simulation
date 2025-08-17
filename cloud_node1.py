from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud_node1",
        disk_path="./assets/cloud_node1/",
        ip_address="192.168.1.6",
        ftp_port=2126
    )
    node.run_interactive()