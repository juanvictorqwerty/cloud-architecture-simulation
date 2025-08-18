from virtual_node import VirtualNode

if __name__ == "__main__":
    node = VirtualNode(
        name="cloud1",
        disk_path="./assets/cloud1/",
        ip_address="192.168.1.101",
        ftp_port=2131
    )
    node.run_interactive()