from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="node4",
        disk_path="./assets/node4/",
        ip_address="192.168.1.4"
    )
    node.run_interactive()