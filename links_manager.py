import json
import os
from config import SERVER_DISK_PATH, IP_MAP

class LinksManager:
    def __init__(self):
        self.links_file = os.path.join(SERVER_DISK_PATH, "links.json")
        self.links = {}
        self._load_links()

    def _load_links(self):
        """Load links from links.json, if it exists."""
        try:
            if os.path.exists(self.links_file):
                with open(self.links_file, 'r') as f:
                    self.links = json.load(f)
            else:
                self.links = {}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading links from {self.links_file}: {e}")
            self.links = {}

    def _save_links(self):
        """Save links to links.json."""
        try:
            with open(self.links_file, 'w') as f:
                json.dump(self.links, f, indent=2)
        except IOError as e:
            print(f"Error saving links to {self.links_file}: {e}")

    def licreate(self, link_name, nodes):
        """Create a link with the given name and nodes."""
        if len(nodes) < 2:
            return f"Error: Link {link_name} requires at least two nodes"
        if link_name in self.links:
            return f"Error: Link {link_name} already exists"
        for node in nodes:
            if not any(info["node_name"] == node for info in IP_MAP.values()):
                return f"Error: Node {node} does not exist"
        self.links[link_name] = nodes
        self._save_links()
        return f"Created link {link_name} with nodes {', '.join(nodes)}"

    def delete(self, link_name):
        """Delete the specified link or all links if link_name is 'all'."""
        if link_name == "all":
            self.links = {}
            self._save_links()
            return "Deleted all links"
        if link_name not in self.links:
            return f"Error: Link {link_name} does not exist"
        del self.links[link_name]
        self._save_links()
        return f"Deleted link {link_name}"

    def is_transfer_allowed(self, sender_node, target_node):
        """Check if a transfer between sender_node and target_node is allowed."""
        self._load_links()  # Reload links from links.json to ensure latest state
        for link_nodes in self.links.values():
            if sender_node in link_nodes and target_node in link_nodes:
                return True
        return False

    def run_terminal(self):
        """Run an interactive terminal for managing links."""
        print("Links Manager Terminal. Available commands:")
        print("  licreate <link_name> <node1> <node2> [node3 ...]")
        print("  del <link_name | all>")
        print("  exit (or quit)")
        print("Enter commands below:")
        
        while True:
            try:
                command = input("links_manager>> ").strip().split()
                if not command:
                    continue
                cmd = command[0].lower()
                
                if cmd in ("exit", "quit"):
                    print("Exiting Links Manager Terminal.")
                    break
                elif cmd == "licreate" and len(command) >= 3:
                    link_name = command[1]
                    nodes = command[2:]
                    print(self.licreate(link_name, nodes))
                elif cmd == "del" and len(command) == 2:
                    link_name = command[1]
                    print(self.delete(link_name))
                else:
                    print("Invalid command. Use: licreate <link_name> <node1> <node2> [node3 ...], del <link_name | all>, exit")
            except EOFError:
                print("\nEOF detected. Exiting Links Manager Terminal.")
                break
            except KeyboardInterrupt:
                print("\nKeyboard interrupt detected. Exiting Links Manager Terminal.")
                break
            except Exception as e:
                print(f"Error processing command: {e}")

