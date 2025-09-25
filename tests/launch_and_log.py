import subprocess, os, sys
py = r'F:\Python\Multi-Agent_MCP_GUI_Controller\.venv\Scripts\python.exe'
script = r'F:\Python\Multi-Agent_MCP_GUI_Controller\multi-agent_mcp_gui_controller.py'
log = r'F:\Python\Multi-Agent_MCP_GUI_Controller\tests\gui_runtime_fresh.log'
# remove old log
try:
    os.remove(log)
except FileNotFoundError:
    pass
env = os.environ.copy()
env['MCP_DEBUG'] = '1'
with open(log, 'wb') as f:
    p = subprocess.Popen([py, script], stdout=f, stderr=subprocess.STDOUT, env=env)
    # wait briefly to let it start and possibly produce errors
    try:
        p.wait(timeout=3)
    except subprocess.TimeoutExpired:
        # still running - assume GUI started; write pid and exit
        f.write(b'PROCESS_RUNNING\n')
        f.write(f'PID={p.pid}\n'.encode())
        print('Launched, PID', p.pid)
        sys.exit(0)
    print('Process exited, returncode', p.returncode)
    sys.exit(p.returncode)
