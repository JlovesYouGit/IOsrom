# IOsrom

iOS firmware manipulation and exploitation toolkit for research purposes.

## ⚠️ Disclaimer

This project is for **educational and research purposes only**. Using this software may violate Apple's Terms of Service and End User License Agreements. Use at your own risk.

## Features

- iOS firmware extraction and analysis (iOS 4-9)
- NAND bypass techniques for legacy devices
- TSS server interception and local signing
- Hardware memory mapping and exploitation
- IPSW modification and creation
- Checkm8 exploit integration

## Requirements

- Python 3.8+
- Windows (for Windows-specific tools)
- 3uTools or libimobiledevice
- irecovery, idevicerestore

## Installation

```bash
git clone https://github.com/JlovesYouGit/IOsrom.git
cd IOsrom
pip install -r requirements.txt
```

## Configuration

Set the base directory via environment variable:

```bash
export IOS_TOOLS_BASE="N:/ROMLOADDER"  # or your firmware directory
```

Or modify `utils.py` to set a default path.

## Usage

```bash
# Extract IPSW components
python extract_ipsw_parts.py

# Check IPSW integrity
python check_ipsw_integrity.py <ipsw_file>

# Run custom restore coordinator
python custom_restore_coordinator.py
```

## Project Structure

```
IOsrom/
├── utils.py              # Shared utilities
├── config.py             # Hardware mappings and constants
├── requirements.txt      # Python dependencies
├── extract_*.py          # Firmware extraction tools
├── flash_*.py            # Firmware flashing tools
├── patch_*.py            # Binary patching tools
├── check_*.py            # Validation tools
└── ...                   # Additional tools
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- checkm8 exploit (axi0mx)
- libimobiledevice community
- iOS research community
