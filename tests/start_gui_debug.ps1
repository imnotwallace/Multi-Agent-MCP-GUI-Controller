$env:MCP_DEBUG = '1'
Start-Process -FilePath 'F:\Python\Multi-Agent_MCP_GUI_Controller\.venv\Scripts\python.exe' -ArgumentList 'F:\Python\Multi-Agent_MCP_GUI_Controller\multi-agent_mcp_gui_controller.py' -NoNewWindow
Write-Output 'Started GUI with MCP_DEBUG=1'
