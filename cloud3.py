from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud3",
        disk_path="./assets/cloud3/",
        ip_address="192.168.1.103"
    )
    node.run_interactive()