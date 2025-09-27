# 📋 Claude Code Installation Instructions

## 🚀 **Quick Installation** (Updated with GUI Auto-Launch)

### **Step 1: Install Dependencies**

```bash
pip install fastapi uvicorn websockets requests
```

### **Step 2: Choose Your Configuration**

You now have **two options** for Claude Code integration:

#### **Option A: Server Only (Recommended)**
Best for most users - lightweight, no GUI popup.

Copy this to your Claude Code MCP settings:
```json
{
  "mcpServers": {
    "multi-agent-context-manager": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"],
      "env": {
        "MCP_SERVER_PORT": "8765",
        "MCP_SERVER_HOST": "127.0.0.1",
        "LAUNCH_GUI": "false"
      }
    }
  }
}
```

#### **Option B: Server + Auto-Launch GUI**
Automatically opens the management GUI when Claude Code starts the server.

Copy this to your Claude Code MCP settings:
```json
{
  "mcpServers": {
    "multi-agent-context-manager-with-gui": {
      "command": "python",
      "args": ["run_redesigned_mcp_server.py"],
      "env": {
        "MCP_SERVER_PORT": "8765",
        "MCP_SERVER_HOST": "127.0.0.1",
        "LAUNCH_GUI": "true"
      }
    }
  }
}
```

### **Step 3: Test Installation**

Test the server manually first:

**For Option A (Server Only):**
```bash
python run_redesigned_mcp_server.py
```

**For Option B (Server + GUI):**
```bash
set LAUNCH_GUI=true
python run_redesigned_mcp_server.py
```

You should see:
```
INFO: Starting Multi-Agent MCP Context Manager Server (Redesigned)
INFO: Server will start on 127.0.0.1:8765
INFO: GUI auto-launch enabled (LAUNCH_GUI=true)  # Only for Option B
INFO: Enhanced GUI launched with PID: XXXX       # Only for Option B
INFO: Uvicorn running on http://127.0.0.1:8765
```

Press `Ctrl+C` to stop the test.

### **Step 4: Restart Claude Code**

1. **Save your MCP configuration** in Claude Code settings
2. **Restart Claude Code** completely
3. **Check MCP status** - should show "Connected"

## 🎯 **What Each Option Does**

### **Option A: Server Only**
- ✅ Starts MCP server for Claude Code communication
- ✅ Lightweight, no extra windows
- ✅ Perfect for Claude Code-only usage
- ❌ No visual management interface

### **Option B: Server + GUI**
- ✅ Starts MCP server for Claude Code communication
- ✅ **Automatically opens Enhanced GUI** for management
- ✅ Visual connection/agent assignment interface
- ✅ Real-time status monitoring
- ⚠️ Extra window opens when Claude Code starts server

## 🔧 **Advanced Configuration**

### **Environment Variables**
You can control behavior with these environment variables:

```bash
MCP_SERVER_HOST=127.0.0.1    # Server host (default: 127.0.0.1)
MCP_SERVER_PORT=8765         # Server port (default: 8765)
LAUNCH_GUI=true              # Auto-launch GUI (default: false)
```

### **Manual GUI Launch**
Even with Option A, you can manually launch the GUI anytime:

```bash
python enhanced_gui_module.py
```

## 📝 **Using the System in Claude Code**

Once connected, use these MCP methods:

**Read contexts:**
```
Use ReadDB with agent_id "my_agent" to see available contexts
```

**Write context:**
```
Use WriteDB with agent_id "my_agent" and context "I completed task X"
```

**The system will:**
1. Register unknown connections automatically
2. Allow agent assignment through GUI
3. Enforce permission-based access (self/team/session levels)
4. Provide secure context sharing between agents

## 🔍 **Troubleshooting**

### **Server Won't Start**
```bash
# Check Python and dependencies
python --version
pip list | grep fastapi

# Test manually
python run_redesigned_mcp_server.py
```

### **GUI Won't Launch (Option B)**
- Ensure `enhanced_gui_module.py` exists in same directory
- Check if tkinter is installed: `python -c "import tkinter"`
- Review server logs for GUI launch errors

### **Claude Code Connection Issues**
1. Verify port 8765 isn't in use: `netstat -an | findstr 8765`
2. Check Claude Code MCP settings match exactly
3. Restart Claude Code completely after configuration changes

### **Permission Issues**
- Use the GUI to assign agents to connections (1-to-1 relationship)
- Configure permission levels: self_only, team_level, session_level
- Check agent assignments in GUI "Agent Assignment" tab

## ✅ **Verification Checklist**

- [ ] Dependencies installed (`fastapi uvicorn websockets requests`)
- [ ] Configuration copied to Claude Code MCP settings
- [ ] Server starts manually without errors
- [ ] Claude Code shows "Connected" status
- [ ] Can send ReadDB/WriteDB commands in Claude Code
- [ ] GUI opens (if using Option B)

**You're all set!** The system provides secure, permission-based multi-agent context sharing with optional visual management.