#!/usr/bin/env python3
"""Batch Scanner Application.

Web-based interface for efficient scanning of documents and photos using SANE.
"""

import os
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from flask import Flask, render_template, request, jsonify, send_file, Response
from PIL import Image
from pydantic import BaseModel, Field, validator
import img2pdf

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)


class ScanData(BaseModel):
    """Model for storing scan metadata.

    Attributes:
        path: Filesystem path to the scanned image file.
        timestamp: When the scan was created.
    """

    path: str = Field(..., description="Path to the scanned image file")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Scan creation timestamp"
    )


class ScanSettings(BaseModel):
    """Model for scan configuration settings.

    Attributes:
        resolution: Scan resolution in DPI (150-1200).
        format: Output file format (jpeg, png, tiff, pdf).
        output_folder: Directory where scans will be saved.
        filename_prefix: Prefix for saved filenames.
        page_size: Page size for scanning (A4, Letter, Legal, A3).
    """

    resolution: int = Field(
        default=300, ge=150, le=1200, description="Scan resolution in DPI"
    )
    format: str = Field(default="jpeg", description="Output format")
    output_folder: str = Field(
        default_factory=lambda: str(Path.home() / "scanned_documents")
    )
    filename_prefix: str = Field(default="scan", description="Filename prefix")
    page_size: str = Field(default="A4", description="Page size")

    @validator("format")
    def validate_format(cls, v: str) -> str:
        """Validate and normalize file format.

        Args:
            v: Format string to validate.

        Returns:
            Normalized format string.

        Raises:
            ValueError: If format is not supported.
        """
        allowed = ["jpeg", "jpg", "png", "tiff", "pdf"]
        if v.lower() not in allowed:
            raise ValueError(f"Format must be one of {allowed}")
        return "jpeg" if v.lower() == "jpg" else v.lower()

    @validator("page_size")
    def validate_page_size(cls, v: str) -> str:
        """Validate page size.

        Args:
            v: Page size string to validate.

        Returns:
            Validated page size string.

        Raises:
            ValueError: If page size is not supported.
        """
        allowed = ["A4", "Letter", "Legal", "A3"]
        if v not in allowed:
            raise ValueError(f"Page size must be one of {allowed}")
        return v


class SaveRequest(BaseModel):
    """Model for save request data.

    Attributes:
        scan_ids: List of scan IDs to save.
        format: Output file format.
        output_folder: Destination folder.
        filename_prefix: Prefix for output filename.
    """

    scan_ids: List[str] = Field(
        ..., min_items=1, description="List of scan IDs to save"
    )
    format: str = Field(default="jpeg", description="Output format")
    output_folder: str = Field(..., description="Output folder path")
    filename_prefix: str = Field(default="scan", description="Filename prefix")


class DiscardRequest(BaseModel):
    """Model for discard request data.

    Attributes:
        scan_ids: List of scan IDs to discard.
    """

    scan_ids: List[str] = Field(
        default_factory=list, description="List of scan IDs to discard"
    )


# Session storage - stores temporary scans by ID
scan_storage: Dict[str, ScanData] = {}

# Default settings
default_settings = ScanSettings()


def ensure_output_folder(folder_path: str) -> None:
    """Create output folder if it doesn't exist.

    Args:
        folder_path: Path to the folder to create.
    """
    Path(folder_path).mkdir(parents=True, exist_ok=True)


def get_scanner_devices() -> str:
    """Get list of available SANE scanner devices.

    Returns:
        String containing scanner device information or error message.

    Examples:
        >>> devices = get_scanner_devices()
        >>> 'device' in devices
        True
    """
    try:
        result = subprocess.run(
            ["scanimage", "-L"], capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error detecting scanners: {str(e)}"


def get_page_size_args(page_size: str) -> List[str]:
    """Get scanimage page size arguments.

    Args:
        page_size: Page size identifier (A4, Letter, Legal, A3).

    Returns:
        List of command-line arguments for scanimage, or empty list if unknown.

    Examples:
        >>> get_page_size_args('A4')
        ['-x', '210', '-y', '297']
        >>> get_page_size_args('Unknown')
        []
    """
    sizes: Dict[str, List[str]] = {
        "A4": ["-x", "210", "-y", "297"],
        "Letter": ["-x", "215.9", "-y", "279.4"],
        "Legal": ["-x", "215.9", "-y", "355.6"],
        "A3": ["-x", "297", "-y", "420"],
    }
    return sizes.get(page_size, [])


def scan_image(resolution: int = 300, page_size: str = "A4") -> str:
    """Scan an image using scanimage command.

    Args:
        resolution: Scan resolution in DPI. Defaults to 300.
        page_size: Page size identifier. Defaults to 'A4'.

    Returns:
        Path to the temporary scanned image file (PNM format).

    Raises:
        Exception: If scanning fails or scanner is not available.

    Examples:
        >>> path = scan_image(300, 'A4')
        >>> os.path.exists(path)
        True
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pnm")
    temp_file.close()

    try:
        # Use scanimage to scan
        cmd = [
            "scanimage",
            "--resolution",
            str(resolution),
            "--format",
            "pnm",
            "--output",
            temp_file.name,
        ]

        # Add page size if specified
        size_args = get_page_size_args(page_size)
        if size_args:
            cmd.extend(size_args)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            raise Exception(f"Scan failed: {result.stderr}")

        return temp_file.name
    except Exception as e:
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)
        raise e


def convert_image(input_path: str, output_format: str = "jpeg") -> str:
    """Convert image to desired format.

    Args:
        input_path: Path to the input image file.
        output_format: Desired output format (jpeg, png, tiff). Defaults to 'jpeg'.

    Returns:
        Path to the converted temporary image file.

    Raises:
        Exception: If image conversion fails.

    Examples:
        >>> path = convert_image('/tmp/scan.pnm', 'jpeg')
        >>> path.endswith('.jpeg')
        True
    """
    # Normalize format
    if output_format.lower() == "jpg":
        output_format = "jpeg"

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    temp_file.close()

    img = Image.open(input_path)

    # Convert to RGB if needed (for JPEG)
    if output_format.lower() == "jpeg" and img.mode in ["RGBA", "LA", "P"]:
        img = img.convert("RGB")

    img.save(temp_file.name, format=output_format.upper())
    img.close()

    return temp_file.name


def cleanup_old_scans() -> None:
    """Clean up scans older than 1 hour.

    Iterates through scan_storage and removes scans that are older than 3600 seconds,
    deleting both the storage entry and the associated file.
    """
    now = datetime.now()
    to_delete: List[str] = []

    for scan_id, scan_data in scan_storage.items():
        age = (now - scan_data.timestamp).total_seconds()
        if age > 3600:  # 1 hour
            to_delete.append(scan_id)

    for scan_id in to_delete:
        scan_data = scan_storage.pop(scan_id)
        if os.path.exists(scan_data.path):
            os.remove(scan_data.path)


def store_scan(image_path: str) -> str:
    """Store a scan with a unique ID.

    Args:
        image_path: Filesystem path to the scanned image.

    Returns:
        Unique scan ID (UUID) for retrieving the scan later.

    Examples:
        >>> scan_id = store_scan('/tmp/scan.jpg')
        >>> len(scan_id) == 36  # UUID length
        True
    """
    scan_id = str(uuid.uuid4())
    scan_storage[scan_id] = ScanData(path=image_path)
    cleanup_old_scans()
    return scan_id


def get_scan_path(scan_id: str) -> Optional[str]:
    """Get the file path for a scan ID.

    Args:
        scan_id: Unique scan identifier.

    Returns:
        Filesystem path to the scan, or None if not found.

    Examples:
        >>> path = get_scan_path('invalid-id')
        >>> path is None
        True
    """
    if scan_id in scan_storage:
        return scan_storage[scan_id].path
    return None


def delete_scan(scan_id: str) -> bool:
    """Delete a scan by ID.

    Args:
        scan_id: Unique scan identifier to delete.

    Returns:
        True if scan was deleted, False if scan was not found.

    Examples:
        >>> success = delete_scan('invalid-id')
        >>> success
        False
    """
    if scan_id in scan_storage:
        scan_data = scan_storage.pop(scan_id)
        if os.path.exists(scan_data.path):
            os.remove(scan_data.path)
        return True
    return False


def save_single_image(
    image_path: str, output_folder: str, filename_prefix: str, file_format: str
) -> str:
    """Save a single image file to disk.

    Args:
        image_path: Path to the source image file.
        output_folder: Destination folder for the saved image.
        filename_prefix: Prefix for the output filename.
        file_format: Output file format (jpeg, png, tiff).

    Returns:
        Full path to the saved image file.

    Raises:
        Exception: If image saving fails.

    Examples:
        >>> path = save_single_image('/tmp/img.jpg', '/tmp/output', 'scan', 'jpeg')
        >>> 'scan_' in path
        True
    """
    ensure_output_folder(output_folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    counter = 1

    while True:
        filename = f"{filename_prefix}_{timestamp}_{counter:03d}.{file_format}"
        output_path = os.path.join(output_folder, filename)
        if not os.path.exists(output_path):
            break
        counter += 1

    # Copy the image to the final destination
    img = Image.open(image_path)
    img.save(output_path)
    img.close()

    return output_path


def save_pdf(image_paths: List[str], output_folder: str, filename_prefix: str) -> str:
    """Save multiple images as a single PDF file.

    Args:
        image_paths: List of paths to image files to include in PDF.
        output_folder: Destination folder for the PDF.
        filename_prefix: Prefix for the output filename.

    Returns:
        Full path to the saved PDF file.

    Raises:
        Exception: If PDF creation fails.

    Examples:
        >>> paths = ['/tmp/page1.jpg', '/tmp/page2.jpg']
        >>> pdf = save_pdf(paths, '/tmp/output', 'document')
        >>> pdf.endswith('.pdf')
        True
    """
    ensure_output_folder(output_folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    counter = 1

    while True:
        filename = f"{filename_prefix}_{timestamp}_{counter:03d}.pdf"
        output_path = os.path.join(output_folder, filename)
        if not os.path.exists(output_path):
            break
        counter += 1

    # Convert all images to PDF
    with open(output_path, "wb") as f:
        f.write(img2pdf.convert(image_paths))

    return output_path


@app.route("/")
def index() -> str:
    """Render the main application page.

    Returns:
        Rendered HTML template with default settings.
    """
    return render_template("index.html", settings=default_settings.dict())


@app.route("/api/scan", methods=["POST"])
def scan() -> Tuple[Response, int]:
    """Perform a scan operation.

    Expects JSON request body with:
        - resolution (int, optional): DPI resolution, defaults to 300
        - page_size (str, optional): Page size, defaults to 'A4'

    Returns:
        JSON response containing:
            - success (bool): Whether scan succeeded
            - scan_id (str): Unique identifier for the scan
            - preview_url (str): URL to preview the scan
        Or error response with 500 status code.

    Examples:
        >>> # POST /api/scan with {"resolution": 300, "page_size": "A4"}
        >>> # Returns: {"success": true, "scan_id": "...", "preview_url": "..."}
    """
    data = request.json
    resolution = int(data.get("resolution", 300))
    page_size = data.get("page_size", "A4")

    try:
        # Perform the scan
        scanned_pnm = scan_image(resolution, page_size)

        # Convert to JPEG for preview
        preview_format = "jpeg"
        converted_image = convert_image(scanned_pnm, preview_format)

        # Remove the PNM file
        os.remove(scanned_pnm)

        # Store scan with unique ID
        scan_id = store_scan(converted_image)

        return jsonify(
            {
                "success": True,
                "scan_id": scan_id,
                "preview_url": f"/api/preview/{scan_id}",
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/preview/<scan_id>")
def preview(scan_id: str) -> Tuple[Response, int]:
    """Get scan preview image by ID.

    Args:
        scan_id: Unique scan identifier from URL path.

    Returns:
        JPEG image file or JSON error response with 404 status.

    Examples:
        >>> # GET /api/preview/abc-123-def
        >>> # Returns: JPEG image or 404 error
    """
    image_path = get_scan_path(scan_id)
    if image_path and os.path.exists(image_path):
        return send_file(image_path, mimetype="image/jpeg"), 200
    else:
        return jsonify({"error": "Preview not found"}), 404


@app.route("/api/scanner_info")
def scanner_info() -> Tuple[Response, int]:
    """Get information about available scanners.

    Returns:
        JSON response containing scanner device information.

    Examples:
        >>> # GET /api/scanner_info
        >>> # Returns: {"devices": "device `...` is a ..."}
    """
    devices = get_scanner_devices()
    return jsonify({"devices": devices}), 200


@app.route("/api/save", methods=["POST"])
def save() -> Tuple[Response, int]:
    """Save scans to disk.

    Expects JSON request body with:
        - scan_ids (list[str]): List of scan IDs to save
        - format (str): Output format (jpeg, png, tiff, pdf)
        - output_folder (str): Destination folder path
        - filename_prefix (str): Filename prefix

    Returns:
        JSON response containing:
            - success (bool): Whether save succeeded
            - saved_path (str): Full path to saved file
            - filename (str): Name of saved file
        Or error response with 400/500 status code.

    Examples:
        >>> # POST /api/save with SaveRequest data
        >>> # Returns: {"success": true, "saved_path": "...", "filename": "..."}
    """
    try:
        data = request.json
        save_request = SaveRequest(**data)
    except Exception as e:
        return jsonify({"success": False, "error": f"Invalid request: {str(e)}"}), 400

    try:
        # Get all scan paths
        image_paths: List[str] = []
        for scan_id in save_request.scan_ids:
            path = get_scan_path(scan_id)
            if path:
                image_paths.append(path)

        if not image_paths:
            return jsonify({"success": False, "error": "No valid scans found"}), 400

        # Save based on format
        if save_request.format == "pdf":
            # Single or multi-page PDF
            saved_path = save_pdf(
                image_paths, save_request.output_folder, save_request.filename_prefix
            )
        else:
            # Single image file
            saved_path = save_single_image(
                image_paths[0],
                save_request.output_folder,
                save_request.filename_prefix,
                save_request.format,
            )

        # Clean up saved scans
        for scan_id in save_request.scan_ids:
            delete_scan(scan_id)

        return jsonify(
            {
                "success": True,
                "saved_path": saved_path,
                "filename": os.path.basename(saved_path),
            }
        ), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

        return jsonify(
            {
                "success": True,
                "saved_path": saved_path,
                "filename": os.path.basename(saved_path),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/discard", methods=["POST"])
def discard() -> Tuple[Response, int]:
    """Discard scans without saving.

    Expects JSON request body with:
        - scan_ids (list[str]): List of scan IDs to discard

    Returns:
        JSON response containing:
            - success (bool): Always true
            - deleted_count (int): Number of scans deleted

    Examples:
        >>> # POST /api/discard with {"scan_ids": ["id1", "id2"]}
        >>> # Returns: {"success": true, "deleted_count": 2}
    """
    try:
        data = request.json
        discard_request = DiscardRequest(**data)
    except Exception as e:
        return jsonify({"success": False, "error": f"Invalid request: {str(e)}"}), 400

    deleted_count = 0
    for scan_id in discard_request.scan_ids:
        if delete_scan(scan_id):
            deleted_count += 1

    return jsonify({"success": True, "deleted_count": deleted_count}), 200


if __name__ == "__main__":
    print("=" * 60)
    print("Batch Scanner Application")
    print("=" * 60)
    print("\nChecking for available scanners...")
    print(get_scanner_devices())
    print("\nStarting web interface on http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    app.run(debug=True, host="0.0.0.0", port=5000)
