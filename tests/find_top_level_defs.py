p='f:/Python/Multi-Agent_MCP_GUI_Controller/multi-agent_mcp_gui_controller.py'
with open(p,'r',encoding='utf-8') as f:
    for i,l in enumerate(f, start=1):
        if l.lstrip().startswith('def ') and not l.startswith('    '):
            print(i, l.rstrip())
