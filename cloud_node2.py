from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud_node2",
        disk_path="./assets/cloud_node2/",
        ip_address="192.168.1.7",
        ftp_port=2127
    )
    node.run_interactive()