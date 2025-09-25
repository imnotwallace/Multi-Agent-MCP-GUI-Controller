import runpy, traceback, sys, os
log='f:/Python/Multi-Agent_MCP_GUI_Controller/tests/gui_direct.log'
try:
    m = runpy.run_path('f:/Python/Multi-Agent_MCP_GUI_Controller/multi-agent_mcp_gui_controller.py')
    cls = m['MultiAgentMCPManager']
    app = cls()
    print('App created; starting mainloop')
    app.root.mainloop()
except Exception:
    with open(log,'w',encoding='utf-8') as f:
        traceback.print_exc(file=f)
    print('Exception written to', log)
    sys.exit(1)
