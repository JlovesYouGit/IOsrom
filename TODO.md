# TODO List for IOsrom

## High Priority
- [ ] Add comprehensive unit tests for core utilities
- [ ] Replace all bare `except:` clauses with specific exceptions
- [ ] Remove hardcoded paths and use configuration
- [ ] Add type hints to all Python files
- [ ] Create proper package structure (`ios_tools/`)

## Medium Priority
- [ ] Separate simulation code from production code
- [ ] Add input validation for all user inputs
- [ ] Implement proper logging framework across all scripts
- [ ] Add CI/CD pipeline for testing
- [ ] Document security implications of each tool
- [ ] Add checksum verification for firmware files

## Low Priority
- [ ] Standardize naming conventions
- [ ] Add docstrings to all functions
- [ ] Create API documentation
- [ ] Add Windows/Linux compatibility layer
- [ ] Optimize memory usage in extraction tools

## Completed
- [x] Create shared utilities module (`utils.py`)
- [x] Add `requirements.txt`
- [x] Add GitHub Actions CI/CD
- [x] Create README
- [x] Fix critical security issues in `bypass_itunes_server.py`
