from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud2",
        disk_path="./assets/cloud2/",
        ip_address="192.168.1.102",
        ftp_port=2132
    )
    node.run_interactive()