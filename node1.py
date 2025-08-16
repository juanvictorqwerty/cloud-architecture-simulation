from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="node1",
        disk_path="./assets/node1/",
        ip_address="192.168.1.1",
        ftp_port=2121
    )
    node.run_interactive()