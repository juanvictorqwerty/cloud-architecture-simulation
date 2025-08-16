from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="node2",
        disk_path="./assets/node2/",
        ip_address="192.168.1.2",
        ftp_port=2122
    )
    node.run_interactive()