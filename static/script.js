// State management
let isScanning = false;
let scanIds = [];  // Array of scan IDs
let currentScanId = null;  // Currently displayed scan
let isPdfMode = false;

// DOM elements
const scanBtn = document.getElementById('scan-btn');
const saveBtn = document.getElementById('save-btn');
const appendBtn = document.getElementById('append-btn');
const discardBtn = document.getElementById('discard-btn');
const previewImage = document.getElementById('preview-image');
const previewPlaceholder = document.getElementById('preview-placeholder');
const statusMessage = document.getElementById('status-message');
const formatSelect = document.getElementById('format');
const pdfInfo = document.getElementById('pdf-info');
const pdfPageCountSpan = document.getElementById('pdf-page-count');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkScannerStatus();
    setupEventListeners();
    updatePdfModeUI();
});

// Check for available scanners
async function checkScannerStatus() {
    try {
        const response = await fetch('/api/scanner_info');
        const data = await response.json();
        const scannerInfo = document.getElementById('scanner-info');
        
        if (data.devices && data.devices.includes('device')) {
            scannerInfo.textContent = '✓ Scanner detected';
            scannerInfo.className = 'status-success';
        } else {
            scannerInfo.textContent = '⚠ No scanner detected';
            scannerInfo.className = 'status-warning';
        }
    } catch (error) {
        console.error('Error checking scanner:', error);
        document.getElementById('scanner-info').textContent = '✗ Error checking scanner';
    }
}

// Setup event listeners
function setupEventListeners() {
    scanBtn.addEventListener('click', () => performScan());
    saveBtn.addEventListener('click', () => saveCurrent());
    appendBtn.addEventListener('click', () => performScan());
    discardBtn.addEventListener('click', discardAll);
    
    formatSelect.addEventListener('change', updatePdfModeUI);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ignore if typing in input field
        if (e.target.tagName === 'INPUT') return;
        
        switch(e.key.toLowerCase()) {
            case 'enter':
                e.preventDefault();
                if (!isScanning) performScan();
                break;
            case 's':
                e.preventDefault();
                if (!isScanning && currentScanId) saveCurrent();
                break;
            case 'a':
                e.preventDefault();
                if (!isScanning && isPdfMode) performScan();
                break;
            case 'd':
                e.preventDefault();
                if (!isScanning && scanIds.length > 0) discardAll();
                break;
        }
    });
}

// Update UI based on PDF mode
function updatePdfModeUI() {
    isPdfMode = formatSelect.value === 'pdf';
    
    if (isPdfMode) {
        appendBtn.style.display = 'inline-block';
        pdfInfo.style.display = 'block';
    } else {
        appendBtn.style.display = 'none';
        pdfInfo.style.display = 'none';
    }
}

// Perform scan operation
async function performScan() {
    if (isScanning) return;
    
    // If there are existing scans, save them first
    if (scanIds.length > 0) {
        await saveCurrent();
        // If save failed, scanIds will still have items - don't proceed with scan
        if (scanIds.length > 0) return;
    }
    
    isScanning = true;
    updateButtonStates();
    showStatus('Scanning...', 'info');
    
    const settings = {
        resolution: parseInt(document.getElementById('resolution').value),
        page_size: document.getElementById('page_size').value,
        auto_trim: document.getElementById('auto_trim').checked
    };
    
    try {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Add scan ID to our list
            scanIds.push(data.scan_id);
            currentScanId = data.scan_id;
            
            // Load preview
            previewImage.src = data.preview_url;
            previewImage.style.display = 'block';
            previewPlaceholder.style.display = 'none';
            
            // Update PDF page count
            if (isPdfMode) {
                pdfPageCountSpan.textContent = scanIds.length;
                showStatus(`Page ${scanIds.length} scanned. Press A for next page or S to save PDF.`, 'success');
            } else {
                showStatus('Scan complete. Press S to save or Enter to scan next.', 'success');
            }
        } else {
            showStatus(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    } finally {
        isScanning = false;
        updateButtonStates();
    }
}

// Save current scan(s)
async function saveCurrent() {
    if (isScanning || scanIds.length === 0) return;
    
    showStatus('Saving...', 'info');
    
    const settings = {
        scan_ids: scanIds,
        format: document.getElementById('format').value,
        output_folder: document.getElementById('output_folder').value,
        filename_prefix: document.getElementById('filename_prefix').value
    };
    
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`Saved: ${data.filename}`, 'success');
            
            // Reset state
            scanIds = [];
            currentScanId = null;
            previewImage.style.display = 'none';
            previewPlaceholder.style.display = 'flex';
            
            if (isPdfMode) {
                pdfPageCountSpan.textContent = 0;
            }
            
            updateButtonStates();
        } else {
            showStatus(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}

// Discard all scans
async function discardAll() {
    if (isScanning || scanIds.length === 0) return;
    
    try {
        const response = await fetch('/api/discard', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ scan_ids: scanIds })
        });
        
        const data = await response.json();
        
        if (data.success) {
            scanIds = [];
            currentScanId = null;
            previewImage.style.display = 'none';
            previewPlaceholder.style.display = 'flex';
            
            if (isPdfMode) {
                pdfPageCountSpan.textContent = 0;
            }
            
            showStatus(`${data.deleted_count} scan(s) discarded`, 'info');
            updateButtonStates();
        }
    } catch (error) {
        showStatus(`Error: ${error.message}`, 'error');
    }
}

// Update button states
function updateButtonStates() {
    scanBtn.disabled = isScanning;
    saveBtn.disabled = isScanning || scanIds.length === 0;
    appendBtn.disabled = isScanning;
    discardBtn.disabled = isScanning || scanIds.length === 0;
    
    if (isScanning) {
        scanBtn.textContent = '⏳ Scanning...';
    } else {
        scanBtn.textContent = '🖨️ Scan (Enter)';
    }
}

// Show status message
function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message status-${type}`;
    statusMessage.style.display = 'block';
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success' || type === 'info') {
        setTimeout(() => {
            statusMessage.style.display = 'none';
        }, 5000);
    }
}
