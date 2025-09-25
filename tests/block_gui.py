import time
import runpy
import threading
import os

# import module and get class
m = runpy.run_path('f:/Python/Multi-Agent_MCP_GUI_Controller/multi-agent_mcp_gui_controller.py')
cls = m['MultiAgentMCPManager']

# instantiate
app = cls()

# write status
with open('f:/Python/Multi-Agent_MCP_GUI_Controller/tests/block_gui.log', 'w') as f:
    f.write('app created\n')

# run mainloop in a thread so we can sleep here
t = threading.Thread(target=app.root.mainloop, daemon=True)
t.start()

with open('f:/Python/Multi-Agent_MCP_GUI_Controller/tests/block_gui.log', 'a') as f:
    f.write('mainloop started, sleeping 20s\n')

try:
    time.sleep(20)
finally:
    # attempt to destroy window
    try:
        app.root.destroy()
    except Exception:
        pass
    with open('f:/Python/Multi-Agent_MCP_GUI_Controller/tests/block_gui.log', 'a') as f:
        f.write('exiting\n')
