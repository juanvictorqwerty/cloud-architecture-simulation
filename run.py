import subprocess
import platform
import os
import time

def run_files(script_path):
    #run the files at once:

    full_path = os.path.abspath(script_path)
    print("Start of operations")

    #command to launch it
    command=['python',full_path]

    #depending on the OS

    if platform.system()=='Windows':
        # We join the command with a space to form a valid command string like "python script.py"
        subprocess.Popen(['start', 'cmd', '/k', ' '.join(command)], shell=True)
    else: # Linux or macOS
        # Use gnome-terminal for Linux, or osascript for macOS to open a new terminal window
        # This is a basic example and might need adjustments based on the specific terminal emulator
        subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', ' '.join(command) + '; exec bash'])
    print(script_path)
scriptList=['router.py','node1.py','node2.py','cloud1.py','cloud2.py','cloud3.py']
print("tonton")

#launch every one
for script in scriptList:
    run_files(script)
    print(f">> {script} run successfully")
    #mini pause
    time.sleep(1)

print()
