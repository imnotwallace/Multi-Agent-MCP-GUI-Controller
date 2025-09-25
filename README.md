# Multi-Agent MCP GUI Controller

A hierarchical context management system for Multi-Agent MCP (Model Context Protocol) interactions with advanced team management and bulk operations.

## 🚀 New Features

- **Team Management**: Create teams, assign agents to teams
- **Multi-Agent Selection**: Select multiple agents with Ctrl+Click
- **Bulk Operations**:
  - Assign multiple agents to teams or sessions
  - Bulk disconnect agents
  - Mass team unassignment
- **Agent Renaming**: Double-click agents to rename them
- **Performance Enhanced**: TTL caching, connection pooling, background operations

## Features

- **Hierarchical Organization**: Projects → Sessions → Teams → Agents
- **Advanced Team System**: Named teams with session association
- **Bulk Agent Management**: Multi-select and bulk operations
- **Database Management**: SQLite with soft deletes and foreign key constraints
- **Performance Optimizations**: Caching, connection pooling, lazy loading
- **Modern GUI**: Multi-tab interface with Agent Management and Team Management

## Files

- `main.py` - **Main application** (performance-enhanced with new features)
- `archive/` - Archived older versions for reference
- `test_new_features.py` - Tests for team and bulk operation features
- `requirements.txt` - Dependencies

## Quick Start

### Installation
```bash
# Install required dependency
pip install cachetools

# Or use virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install cachetools
```

### Run Application
```bash
python main.py
```

## Testing

```bash
python test_new_features.py  # Test new features
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