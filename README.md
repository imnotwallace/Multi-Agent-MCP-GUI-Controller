# Multi-Agent MCP GUI Controller

A hierarchical context management system for Multi-Agent MCP (Model Context Protocol) interactions with a modern GUI interface.

## Features

- **Hierarchical Organization**: Projects → Sessions → Agents
- **Multiple Architectures**: Original, Refactored MVC, Performance-Enhanced
- **Database Management**: SQLite with soft deletes and foreign key constraints
- **Input Validation**: Comprehensive validation with error handling
- **Performance Optimizations**: Caching, connection pooling, lazy loading
- **GUI Interface**: Three-tab interface for project, agent, and data views

## Files

- `multi-agent_mcp_gui_controller.py` - Original implementation with fixes
- `mcp_refactored.py` - Clean MVC architecture version
- `performance_enhanced.py` - High-performance version with caching
- `test_functionality.py` - Comprehensive test suite
- `requirements.txt` - Dependencies

## Quick Start

### Basic Version
```bash
python multi-agent_mcp_gui_controller.py
```

### MVC Version
```bash
python mcp_refactored.py
```

### Performance Version
```bash
pip install cachetools
python performance_enhanced.py
```

## Testing

```bash
python test_functionality.py
```

## Database Schema

- **projects**: Project definitions with soft delete
- **sessions**: Sessions within projects
- **agents**: Agent instances with status tracking
- **contexts**: Context data with sequence tracking

## Architecture Versions

### 1. Original (Fixed)
- Fixed duplicate method issues
- Added input validation
- Improved error handling
- Added logging

### 2. MVC Refactored
- Separated Model, View, Controller
- Clean data access layer
- Better error handling
- Modular design

### 3. Performance Enhanced
- TTL caching system
- Connection pooling
- Lazy loading UI
- Background operations
- Performance monitoring

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details