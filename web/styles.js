// Add CSS styles
const style = document.createElement('style');
style.textContent = `
.fs-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10000;
}

.fs-modal-content {
    background: var(--comfy-menu-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    width: 800px;
    max-width: 90vw;
    height: 650px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
}

.fs-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-color);
}

.fs-breadcrumb {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 14px;
    color: var(--input-text);
    margin-bottom: 15px;
    padding: 8px 0;
}

.fs-breadcrumb-item {
    cursor: pointer;
    color: #007bff;
    text-decoration: none;
}

.fs-breadcrumb-item:hover {
    text-decoration: underline;
}

.fs-breadcrumb-separator {
    color: var(--input-text);
}

.fs-actions {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
}

.fs-btn {
    padding: 8px 14px; /* Slightly larger padding for better touch targets */
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px; /* Slightly larger font */
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap; /* Prevent button text wrapping */
}

.fs-btn-primary {
    background-color: #007bff;
    color: white;
}

.fs-btn-primary:hover {
    background-color: #0056b3;
}

.fs-btn-danger {
    background-color: #dc3545;
    color: white;
}

.fs-btn-danger:hover {
    background-color: #a71e2a;
}

.fs-btn-secondary {
    background-color: #6c757d;
    color: white;
}

.fs-btn-secondary:hover {
    background-color: #545b62;
}

.fs-btn-secondary:disabled {
    background-color: #6c757d;
    opacity: 0.6;
    cursor: not-allowed;
}

.fs-content {
    flex: 1;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--comfy-input-bg);
}

.fs-table {
    width: 100%;
    border-collapse: collapse;
}

.fs-table th,
.fs-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
    color: var(--input-text);
    vertical-align: middle; /* Ensure vertical alignment for icons */
}

.fs-table th {
    background-color: var(--comfy-menu-bg);
    font-weight: bold;
    position: sticky;
    top: 0;
}

.fs-table tr:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

.fs-item {
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
}

.fs-item-icon {
    width: 16px;
    height: 16px;
    flex-shrink: 0;
}

.fs-item-name-link {
    cursor: pointer;
    color: #007bff; /* Or inherit from breadcrumb-item */
    text-decoration: none;
}

.fs-item-name-link:hover {
    text-decoration: underline;
}

.fs-item-selected {
    background-color: rgba(0, 123, 255, 0.2);
}

.fs-item-actions-trigger {
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.fs-item-actions-trigger:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

.fs-item-context-menu {
    position: absolute;
    background-color: var(--comfy-menu-bg);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    z-index: 10001; /* Above modal content */
    min-width: 150px;
    padding: 5px 0;
}

.fs-item-context-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    color: var(--input-text);
    font-size: 13px;
}

.fs-item-context-menu-item:hover {
    background-color: rgba(0, 123, 255, 0.1);
}

.fs-item-context-menu-item svg {
    width: 14px;
    height: 14px;
    fill: currentColor;
}

.fs-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 15px;
    padding-top: 10px;
    border-top: 1px solid var(--border-color);
}

.fs-message {
    padding: 8px 12px;
    border-radius: 4px;
    margin-bottom: 10px;
}

.fs-error {
    background-color: rgba(220, 53, 69, 0.1);
    border: 1px solid rgba(220, 53, 69, 0.3);
    color: #dc3545;
}

.fs-success {
    background-color: rgba(40, 167, 69, 0.1);
    border: 1px solid rgba(40, 167, 69, 0.3);
    color: #28a745;
}

.fs-create-folder-form {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
}

.fs-create-folder-input {
    flex: 1;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--comfy-input-bg);
    color: var(--input-text);
}

.fs-rename-form {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
}

.fs-rename-input {
    flex: 1;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--comfy-input-bg);
    color: var(--input-text);
}

.fs-icon {
    width: 20px;
    height: 20px;
    fill: currentColor;
}

.fs-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.8);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10001;
}

.fs-dialog {
    background: var(--comfy-menu-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    min-width: 400px;
    max-width: 600px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.fs-dialog-danger {
    border-color: #dc3545;
}

.fs-dialog-warning {
    border-color: #ffc107;
}

.fs-dialog-header {
    padding: 20px 20px 10px 20px;
    border-bottom: 1px solid var(--border-color);
}

.fs-dialog-title {
    margin: 0;
    color: var(--input-text);
    font-size: 16px;
    font-weight: bold;
}

.fs-dialog-danger .fs-dialog-title {
    color: #dc3545;
}

.fs-dialog-warning .fs-dialog-title {
    color: #ffc107;
}

.fs-dialog-content {
    padding: 20px;
}

.fs-dialog-message {
    margin: 0;
    color: var(--input-text);
    line-height: 1.4;
}

.fs-dialog-actions {
    padding: 10px 20px 20px 20px;
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}

.fs-dialog-btn {
    min-width: 80px;
    text-align: center;
    justify-content: center;
}

.fs-download-modal {
    width: 700px;
    height: 500px;
}

.fs-upload-modal {
    width: 700px;
    height: 700px;
    max-height: 85vh;
    overflow: auto; /* Prevent content from overflowing */
}

.comfyui-menu-right {
    display: flex;
    align-items: center;
    min-height: 100px
}

.fs-download-view {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.fs-upload-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: auto;
}

.fs-download-options-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    padding: 20px;
}

.fs-upload-options-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    padding: 20px;
    overflow-y: auto;
    flex: 1;
}

.fs-download-option {
    background: var(--comfy-input-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
    color: var(--input-text);
}

.fs-upload-option {
    background: var(--comfy-input-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
    color: var(--input-text);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    min-height: 120px;
    max-height: 150px;
}

.fs-download-option:hover {
    background: rgba(0, 123, 255, 0.1);
    border-color: #007bff;
}

.fs-upload-option:hover {
    background: rgba(0, 123, 255, 0.1);
    border-color: #007bff;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.fs-download-option-icon {
    font-size: 32px;
    margin-bottom: 10px;
}

.fs-upload-option-icon {
    font-size: 40px;
    margin-bottom: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
}

.fs-upload-option-icon svg {
    width: 40px;
    height: 40px;
}

.fs-download-option-title {
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 8px;
}

.fs-upload-option-title {
    font-size: 15px;
    font-weight: bold;
    margin-bottom: 6px;
    color: var(--input-text);
}

.fs-download-option-desc {
    font-size: 12px;
    opacity: 0.8;
    line-height: 1.3;
}

.fs-upload-option-desc {
    font-size: 12px;
    opacity: 0.75;
    line-height: 1.3;
    color: var(--input-text);
    text-align: center;
    max-width: 180px;
}

.fs-download-form-header {
    padding: 0 0 15px 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 20px;
}

.fs-upload-form-header {
    padding: 0 0 15px 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 20px;
    display: flex; /* Added for alignment */
    align-items: center; /* Added for alignment */
}

.fs-download-form-content {
    flex: 1;
    padding: 0 20px;
}

.fs-upload-form-content {
    flex: 1;
    padding: 0 20px;
    overflow-y: auto; /* Allow content to scroll if it overflows */
    max-height: calc(100% - 120px); /* Reserve space for header and actions */
}

.fs-upload-destination-info {
    padding: 8px 0px;
    margin-bottom: 10px;
    font-size: 13px;
    color: var(--input-text);
    background-color: var(--comfy-input-bg);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    text-align: center;
}

.fs-form-group {
    margin-bottom: 16px; /* Reduced from 18px for better fit */
    position: relative; /* For tooltip positioning */
}

.fs-form-group label {
    display: block;
    margin-bottom: 5px; /* Reduced from 6px */
    color: var(--input-text);
    font-size: 13px; /* Slightly smaller label */
    font-weight: 500; /* Medium weight for labels */
}

.fs-form-input,
.fs-upload-modal .fs-form-group input[type="text"],
.fs-upload-modal .fs-form-group input[type="password"] {
    width: 100%;
    padding: 8px 10px; /* Reduced padding for better fit */
    border: 1px solid var(--border-color);
    border-radius: 5px; /* Slightly more rounded corners */
    background-color: var(--comfy-input-bg);
    color: var(--input-text);
    box-sizing: border-box;
    font-size: 14px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    /* Prevent browser validation tooltips from overflowing */
    position: relative;
    z-index: 1;
}

.fs-form-input:focus,
.fs-upload-modal .fs-form-group input[type="text"]:focus,
.fs-upload-modal .fs-form-group input[type="password"]:focus {
    border-color: #007bff; /* Highlight focus */
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
    outline: none;
}

.fs-input-error {
    border-color: #dc3545 !important; /* Red border for error */
    box-shadow: 0 0 0 2px rgba(220, 53, 69, 0.2) !important; /* Red shadow for error */
}


/* Override browser validation styling */
.fs-form-input:invalid,
.fs-upload-modal .fs-form-group input[type="text"]:invalid,
.fs-upload-modal .fs-form-group input[type="password"]:invalid {
    border-color: #dc3545;
    box-shadow: 0 0 0 2px rgba(220, 53, 69, 0.2);
}

.fs-checkbox-form-group {
    margin-bottom: 10px; /* Reduced margin for checkbox groups */
}

.fs-checkbox-group {
    display: flex;
    align-items: center;
    gap: 8px; /* Space between checkbox and label */
    padding: 4px 0; /* Add some vertical padding */
}

.fs-checkbox-group input[type="checkbox"] {
    width: 16px; /* Explicit size */
    height: 16px; /* Explicit size */
    accent-color: #007bff; /* Modern accent for checkbox */
    cursor: pointer;
    flex-shrink: 0; /* Prevent checkbox from shrinking */
}

.fs-checkbox-group label {
    margin-bottom: 0; /* Reset margin for label within checkbox group */
    font-weight: normal; /* Normal weight for checkbox labels */
    font-size: 14px;
    color: var(--input-text);
    cursor: pointer;
    flex: 1; /* Allow label to take remaining space */
}

/* Upload progress styling improvements */
.fs-upload-progress {
    margin-top: 12px; /* Reduced margin */
    padding: 12px; /* Reduced padding */
    background-color: var(--comfy-input-bg);
    border: 1px solid var(--border-color);
    border-radius: 5px;
}

.fs-upload-progress-text {
    margin-bottom: 8px;
    color: var(--input-text);
    font-size: 13px; /* Slightly smaller text */
    line-height: 1.4;
}

.fs-upload-progress-bar {
    width: 100%;
    height: 6px; /* Reduced height */
    background-color: var(--border-color);
    border-radius: 3px;
    overflow: hidden;
}

.fs-upload-progress-fill {
    height: 100%;
    background-color: #007bff;
    width: 0%;
    transition: width 0.2s ease-in-out;
}

/* Message styling improvements */
#fs-upload-message {
    margin-top: 8px; /* Reduced margin */
    padding: 8px 10px; /* Reduced padding */
    border-radius: 4px;
    font-size: 13px; /* Smaller text */
    line-height: 1.4;
    word-wrap: break-word;
    max-height: 80px; /* Increased height for longer messages */
    overflow-y: auto; /* Allow scrolling for long messages */
}

/* Support for HTML content in messages */
#fs-upload-message br {
    line-height: 1.6;
}

/* HF Token input styling */
#fs-hf-token-group {
    background-color: rgba(255, 193, 7, 0.1);
    border: 1px solid rgba(255, 193, 7, 0.3);
    border-radius: 5px;
    padding: 12px;
    margin-top: 8px;
}

#fs-hf-token-group label {
    color: #ffc107;
    font-weight: 600;
}

#fs-hf-token-group small {
    font-style: italic;
}

/* CivitAI Token input styling */
#fs-civitai-token-group {
    background-color: rgba(220, 53, 69, 0.1);
    border: 1px solid rgba(220, 53, 69, 0.3);
    border-radius: 5px;
    padding: 12px;
    margin-top: 8px;
}

#fs-civitai-token-group label {
    color: #dc3545;
    font-weight: 600;
}

#fs-civitai-token-group small {
    font-style: italic;
}

/* Ensure modal content doesn't exceed viewport */
@media (max-height: 600px) {
    .fs-upload-modal {
        height: 90vh;
        max-height: 90vh;
    }
    
    .fs-upload-form-content {
        max-height: calc(100% - 100px);
    }
    
    .fs-form-group {
        margin-bottom: 12px;
    }
    
    .fs-checkbox-form-group {
        margin-bottom: 8px;
    }
}

.fs-upload-form-actions {
    padding: 10px 20px 20px 20px;
    display: flex;
    justify-content: space-between; /* Changed from flex-end to space-between */
    gap: 10px;
}

/* Ensure the buttons maintain their order with Cancel on left, Start Upload on right */
.fs-upload-form-actions #fs-upload-start {
    order: 2; /* Changed from 1 to 2 to move to right */
}

.fs-upload-form-actions #fs-upload-cancel {
    order: 1; /* Changed from 2 to 1 to move to left */
}
`;
document.head.appendChild(style);
