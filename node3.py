from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="node3",
        disk_path="./assets/node3/",
        ip_address="192.168.1.3",
        ftp_port=2123
    )
    node.run_interactive()