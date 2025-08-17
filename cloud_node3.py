from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud_node3",
        disk_path="./assets/cloud_node3/",
        ip_address="192.168.1.8",
        ftp_port=2128
    )
    node.run_interactive()