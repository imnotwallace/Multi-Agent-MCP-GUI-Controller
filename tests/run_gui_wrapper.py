import runpy
import traceback
import sys

log_path = "f:/Python/Multi-Agent_MCP_GUI_Controller/tests/gui_run2.log"
try:
    runpy.run_path('f:/Python/Multi-Agent_MCP_GUI_Controller/multi-agent_mcp_gui_controller.py', run_name='__main__')
except Exception:
    with open(log_path, 'w', encoding='utf-8') as f:
        traceback.print_exc(file=f)
    print(f"Exception captured to {log_path}")
    sys.exit(1)
