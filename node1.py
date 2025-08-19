from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="node1",
        disk_path="./assets/node1/",
        ip_address="192.168.1.1"
    )
    node.run_interactive()