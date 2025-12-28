# Batch Scanner

A Python-based web application for efficient batch scanning of documents and photos using a USB scanner on Debian/Ubuntu Linux.

## Features

- 🖨️ **Web-based Interface** - Control your scanner from any browser
- ⚡ **Quick Scanning** - Press Enter to scan, minimal clicks required
- 👁️ **Live Preview** - See each scan before saving
- � **Flexible Saving** - Save current scan or continue scanning
- 📄 **Multi-page PDFs** - Scan multiple pages and save as single PDF
- ⚙️ **Configurable Settings** - Resolution, format, output folder, filename prefix, page size
- ⌨️ **Keyboard Shortcuts** - Efficient workflow with hotkeys
- 🔄 **Session Management** - Scans stored with unique IDs for better reliability

## Requirements

### System Requirements
- Debian or Ubuntu Linux
- USB scanner supported by SANE
- Python 3.8 or higher

### System Dependencies

Install SANE scanner utilities:
```bash
sudo apt update
sudo apt install sane-utils libsane-dev
```

Verify your scanner is detected:
```bash
scanimage -L
```

## Installation

1. **Clone or download this repository**
   ```bash
   cd /home/marc/dev/batch_scanner
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Connect your USB scanner** and ensure it's powered on

2. **Start the application**
   ```bash
   python3 app.py
   ```

3. **Open your web browser** and navigate to:
   ```
   http://localhost:5000
   ```

4. **Configure settings** in the left panel:
   - Resolution (150-1200 DPI)
   - File format (JPEG, PNG, TIFF, PDF)
   - Page size (A4, Letter, Legal, A3)
   - Output folder
   - Filename prefix

5. **Start scanning:**
   - Press **Enter** or click **Scan** to scan a document
   - Preview appears
   - Press **S** or click **Save Current** to save immediately
   - Or press **Enter** again to scan another page
   - For PDFs: Press **A** or click **Append Page** to add multiple pages before saving

## Keyboard Shortcuts

- **Enter** - Scan document
- **S** - Save current scan(s)
- **A** - Append page (PDF mode or continue scanning)
- **D** - Discard all unsaved scans

## Workflow

### Single-Page Documents (JPEG/PNG/TIFF)

1. Press Enter to scan
2. Preview appears
3. Press S to save immediately, or
4. Press Enter to scan another page
5. Press S when ready to save all scans

### Multi-Page PDF Documents

1. Select "PDF" as file format
2. Press Enter to scan first page
3. Press A (Append) or Enter to scan additional pages
4. All scans are accumulated
5. Press S to save all pages as a single PDF

### Workflow Tips

- Each scan is stored with a unique ID
- Scans are held in memory until saved or discarded
- You can scan multiple documents before saving
- Press D to discard all unsaved scans and start over

## File Naming

Files are automatically named with the pattern:
```
{prefix}_{timestamp}_{counter}.{format}
```

Example: `scan_20231228_143022_001.jpg`

## Troubleshooting

### Scanner not detected
```bash
# Check if scanner is detected by SANE
scanimage -L

# Check USB connection
lsusb

# You may need to add your user to the scanner group
sudo usermod -a -G scanner $USER
# Then log out and log back in
```

### Permission denied errors
```bash
# Ensure your user has permission to access the scanner
sudo chmod 666 /dev/bus/usb/*/*
```

### Scanner works but slow
- Try reducing resolution
- Some scanners perform better with specific formats
- Check scanner manufacturer documentation

## Configuration

Default output folder: `~/scanned_documents`

You can change this in the web interface or modify the `default_settings` in [app.py](app.py).

## Technical Details

- **Backend**: Flask (Python web framework)
- **Scanner Interface**: SANE (scanimage command-line tool)
- **Image Processing**: Pillow (PIL)
- **PDF Generation**: img2pdf
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## License

This project is open source and available for personal and commercial use.

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## Support

For issues specific to:
- Scanner detection: Check SANE documentation for your scanner model
- Linux permissions: Consult your distribution's documentation
- Application bugs: Open an issue in this repository
