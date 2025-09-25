import runpy
m = runpy.run_path('f:/Python/Multi-Agent_MCP_GUI_Controller/multi-agent_mcp_gui_controller.py')
cls = m.get('MultiAgentMCPManager')
print('Has class:', bool(cls))
print('Has assign_agent attr on class:', hasattr(cls, 'assign_agent'))
print('Has add_agent attr on class:', hasattr(cls, 'add_agent'))
print('List attrs:', [a for a in dir(cls) if a.startswith('assign') or a.startswith('add_')])
