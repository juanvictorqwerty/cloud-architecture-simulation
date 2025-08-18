IP_MAP = {
    "192.168.1.1": {"disk_path": "./assets/node1/", "ftp_port": 2121, "node_name": "node1"},
    "192.168.1.2": {"disk_path": "./assets/node2/", "ftp_port": 2122, "node_name": "node2"},
    "192.168.1.3": {"disk_path": "./assets/node3/", "ftp_port": 2123, "node_name": "node3"},
    "192.168.1.4": {"disk_path": "./assets/node4/", "ftp_port": 2124, "node_name": "node4"},
    "192.168.1.5": {"disk_path": "./assets/node5/", "ftp_port": 2125, "node_name": "node5"},

    # --- cloud nodes (never put in a link) ---
    "192.168.1.101": {"disk_path": "./assets/cloud1/", "ftp_port": 2131, "node_name": "cloud1"},
    "192.168.1.102": {"disk_path": "./assets/cloud2/", "ftp_port": 2132, "node_name": "cloud2"},
    "192.168.1.103": {"disk_path": "./assets/cloud3/", "ftp_port": 2133, "node_name": "cloud3"},
}

SERVER_IP = "127.0.0.1"
SERVER_FTP_PORT = 2120
SERVER_SOCKET_PORT = 9999
SERVER_DISK_PATH = "./assets/server/"

CLOUD_NODES = {"cloud1", "cloud2", "cloud3"}