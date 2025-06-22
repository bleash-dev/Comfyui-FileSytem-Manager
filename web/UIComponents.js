export class UIComponents {
    static createModal() {
        const modal = document.createElement('div');
        modal.className = 'fs-modal';
        modal.innerHTML = `
            <div class="fs-modal-content">
                <div class="fs-header">
                    <h3>File System Manager</h3>
                    <button class="fs-btn fs-btn-secondary" id="fs-close">×</button>
                </div>
                
                <div class="fs-breadcrumb" id="fs-breadcrumb">
                    <span class="fs-breadcrumb-item" data-path="">Home</span>
                </div>
                
                <div class="fs-actions">
                    <button class="fs-btn fs-btn-primary" id="fs-create-folder">
                        📁 New Folder
                    </button>
                    <button class="fs-btn fs-btn-primary" id="fs-upload">
                        ⬆️ Upload File
                    </button>
                    <button class="fs-btn fs-btn-secondary" id="fs-download-selected" disabled>
                        ⬇️ Download
                    </button>
                    <button class="fs-btn fs-btn-secondary" id="fs-rename" disabled>
                        ✏️ Rename
                    </button>
                    <button class="fs-btn fs-btn-danger" id="fs-delete" disabled>
                        🗑️ Delete
                    </button>
                    <button class="fs-btn fs-btn-secondary" id="fs-refresh">
                        🔄 Refresh
                    </button>
                </div>
                
                <div id="fs-create-folder-form" class="fs-create-folder-form" style="display: none;">
                    <input type="text" placeholder="Folder name..." class="fs-create-folder-input" id="fs-folder-name" maxlength="50">
                    <button class="fs-btn fs-btn-primary" id="fs-create-confirm">Create</button>
                    <button class="fs-btn fs-btn-secondary" id="fs-create-cancel">Cancel</button>
                </div>

                <div id="fs-rename-form" class="fs-rename-form" style="display: none;">
                    <input type="text" placeholder="New name..." class="fs-rename-input" id="fs-new-name" maxlength="255">
                    <button class="fs-btn fs-btn-primary" id="fs-rename-confirm">Rename</button>
                    <button class="fs-btn fs-btn-secondary" id="fs-rename-cancel">Cancel</button>
                </div>
                
                <div id="fs-message"></div>
                
                <div class="fs-content">
                    <table class="fs-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Type</th>
                                <th>Size</th>
                                <th>Modified</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="fs-table-body">
                        </tbody>
                    </table>
                </div>
                
                <div class="fs-footer">
                    <span id="fs-status">Ready</span>
                    <span id="fs-item-count">0 items</span>
                </div>
            </div>
        `;
        
        return modal;
    }

    static createUploadModal() {
        const modal = document.createElement('div');
        modal.className = 'fs-modal';
        modal.innerHTML = `
            <div class="fs-modal-content fs-upload-modal">
                <div class="fs-header">
                    <h3 id="fs-upload-title">Upload File</h3>
                    <button class="fs-btn fs-btn-secondary" id="fs-upload-close">×</button>
                </div>
                
                <div id="fs-upload-content">
                    <!-- Upload options view -->
                    <div id="fs-upload-options" class="fs-upload-view">
                        <div class="fs-upload-options-grid">
                            <button class="fs-upload-option" data-type="google-drive">
                                <div class="fs-upload-option-icon">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="32px" height="32px" viewBox="0 0 32 32" fill="none">
                                        <path d="M2 11.9556C2 8.47078 2 6.7284 2.67818 5.39739C3.27473 4.22661 4.22661 3.27473 5.39739 2.67818C6.7284 2 8.47078 2 11.9556 2H20.0444C23.5292 2 25.2716 2 26.6026 2.67818C27.7734 3.27473 28.7253 4.22661 29.3218 5.39739C30 6.7284 30 8.47078 30 11.9556V20.0444C30 23.5292 30 25.2716 29.3218 26.6026C28.7253 27.7734 27.7734 28.7253 26.6026 29.3218C25.2716 30 23.5292 30 20.0444 30H11.9556C8.47078 30 6.7284 30 5.39739 29.3218C4.22661 28.7253 3.27473 27.7734 2.67818 26.6026C2 25.2716 2 23.5292 2 20.0444V11.9556Z" fill="white"/>
                                        <path d="M16.0019 12.4507L12.541 6.34297C12.6559 6.22598 12.7881 6.14924 12.9203 6.09766C11.8998 6.43355 11.4315 7.57961 11.4315 7.57961L5.10895 18.7345C5.01999 19.0843 4.99528 19.4 5.0064 19.6781H11.9072L16.0019 12.4507Z" fill="#34A853"/>
                                        <path d="M16.002 12.4507L20.0967 19.6781H26.9975C27.0086 19.4 26.9839 19.0843 26.8949 18.7345L20.5724 7.57961C20.5724 7.57961 20.1029 6.43355 19.0835 6.09766C19.2145 6.14924 19.3479 6.22598 19.4628 6.34297L16.002 12.4507Z" fill="#FBBC05"/>
                                        <path d="M16.0019 12.4514L19.4628 6.34371C19.3479 6.22671 19.2144 6.14997 19.0835 6.09839C18.9327 6.04933 18.7709 6.01662 18.5954 6.00781H18.4125H13.5913H13.4084C13.2342 6.01536 13.0711 6.04807 12.9203 6.09839C12.7894 6.14997 12.6559 6.22671 12.541 6.34371L16.0019 12.4514Z" fill="#188038"/>
                                        <path d="M11.9082 19.6782L8.48687 25.7168C8.48687 25.7168 8.3732 25.6614 8.21875 25.5469C8.70434 25.9206 9.17633 25.9998 9.17633 25.9998H22.6134C23.3547 25.9998 23.5092 25.7168 23.5092 25.7168C23.5116 25.7155 23.5129 25.7142 23.5153 25.713L20.0965 19.6782H11.9082Z" fill="#4285F4"/>
                                        <path d="M11.9086 19.6782H5.00781C5.04241 20.4985 5.39826 20.9778 5.39826 20.9778L5.65773 21.4281C5.67627 21.4546 5.68739 21.4697 5.68739 21.4697L6.25205 22.461L7.51976 24.6676C7.55683 24.7569 7.60008 24.8386 7.6458 24.9166C7.66309 24.9431 7.67915 24.972 7.69769 24.9972C7.70263 25.0047 7.70757 25.0123 7.71252 25.0198C7.86944 25.2412 8.04489 25.4123 8.22034 25.5469C8.37479 25.6627 8.48847 25.7168 8.48847 25.7168L11.9086 19.6782Z" fill="#1967D2"/>
                                        <path d="M20.0967 19.6782H26.9974C26.9628 20.4985 26.607 20.9778 26.607 20.9778L26.3475 21.4281C26.329 21.4546 26.3179 21.4697 26.3179 21.4697L25.7532 22.461L24.4855 24.6676C24.4484 24.7569 24.4052 24.8386 24.3595 24.9166C24.3422 24.9431 24.3261 24.972 24.3076 24.9972C24.3026 25.0047 24.2977 25.0123 24.2927 25.0198C24.1358 25.2412 23.9604 25.4123 23.7849 25.5469C23.6305 25.6627 23.5168 25.7168 23.5168 25.7168L20.0967 19.6782Z" fill="#EA4335"/>
                                    </svg>
                                </div>
                                <div class="fs-upload-option-title">Google Drive</div>
                                <div class="fs-upload-option-desc">Upload from Google Drive share link</div>
                            </button>
                            
                            <button class="fs-upload-option" data-type="huggingface">
                                <div class="fs-upload-option-icon">🤗</div>
                                <div class="fs-upload-option-title">Hugging Face</div>
                                <div class="fs-upload-option-desc">Upload from Hugging Face repository</div>
                            </button>
                            
                            <button class="fs-upload-option" data-type="civitai">
                                <div class="fs-upload-option-icon">🎨</div>
                                <div class="fs-upload-option-title">Civitai</div>
                                <div class="fs-upload-option-desc">Upload from Civitai model repository</div>
                            </button>
                            
                            <button class="fs-upload-option" data-type="direct-link">
                                <div class="fs-upload-option-icon">🔗</div>
                                <div class="fs-upload-option-title">Direct Link</div>
                                <div class="fs-upload-option-desc">Upload using direct URL</div>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Upload form view -->
                    <div id="fs-upload-form" class="fs-upload-view" style="display: none;">
                        <div class="fs-upload-form-header">
                            <button class="fs-btn fs-btn-secondary" id="fs-upload-back">← Back</button>
                            <h4 id="fs-upload-form-title" style="margin-left: 10px;">Upload</h4>
                        </div>
                        
                        <div class="fs-upload-form-content">
                            <div id="fs-upload-destination-info" class="fs-upload-destination-info" style="display: none;"></div>
                            <!-- Common fields -->
                            <div class="fs-form-group">
                                <label for="fs-upload-url" id="fs-upload-url-label">URL:</label>
                                <input type="text" id="fs-upload-url" class="fs-form-input" placeholder="Enter upload URL...">
                            </div>
                            
                            <!-- Fields specific to upload type will be injected here by showUploadForm -->
                            <div id="fs-upload-type-specific-fields"></div>

                            <!-- Progress display area -->
                            <div id="fs-upload-progress" class="fs-upload-progress" style="display: none; margin-top: 15px;">
                                <div class="fs-upload-progress-text" style="margin-bottom: 5px; color: var(--input-text);">Preparing...</div>
                                <div class="fs-upload-progress-bar" style="width: 100%; height: 8px; background-color: var(--border-color); border-radius: 4px; overflow: hidden;">
                                    <div class="fs-upload-progress-fill" style="height: 100%; background-color: #007bff; width: 0%; transition: width 0.2s ease-in-out;"></div>
                                </div>
                            </div>
                             <div id="fs-upload-message" style="margin-top: 10px;"></div>

                        </div>
                        
                        <div class="fs-upload-form-actions">
                            <button class="fs-btn fs-btn-primary" id="fs-upload-start">Start Upload</button>
                            <button class="fs-btn fs-btn-secondary" id="fs-upload-cancel">Cancel</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return modal;
    }

    static updateBreadcrumb(modal, currentPath, onNavigate) {
        const breadcrumb = modal.querySelector('#fs-breadcrumb');
        breadcrumb.innerHTML = '';
        
        // Home link
        const homeLink = document.createElement('span');
        homeLink.className = 'fs-breadcrumb-item';
        homeLink.textContent = 'Home';
        homeLink.dataset.path = '';
        homeLink.addEventListener('click', (e) => {
            e.preventDefault();
            onNavigate('');
        });
        breadcrumb.appendChild(homeLink);
        
        if (currentPath) {
            const parts = currentPath.split('/').filter(Boolean);
            let currentPath_temp = '';
            
            for (let i = 0; i < parts.length; i++) {
                const part = parts[i];
                
                // Separator
                const separator = document.createElement('span');
                separator.className = 'fs-breadcrumb-separator';
                separator.textContent = ' / ';
                breadcrumb.appendChild(separator);
                
                currentPath_temp += (currentPath_temp ? '/' : '') + part;
                const pathForClick = currentPath_temp;
                
                // Path link
                const pathLink = document.createElement('span');
                pathLink.className = 'fs-breadcrumb-item';
                pathLink.textContent = part;
                pathLink.dataset.path = pathForClick;
                pathLink.addEventListener('click', (e) => {
                    e.preventDefault();
                    onNavigate(pathForClick);
                });
                breadcrumb.appendChild(pathLink);
            }
        }
    }

    static renderContents(modal, contents, onItemClick, onNavigateLinkClick, onActionTriggerClick, onGlobalModelDownload) {
        const tbody = modal.querySelector('#fs-table-body');
        tbody.innerHTML = '';
        
        for (const item of contents) {
            // Skip items with empty or invalid names - be more strict
            if (!item.name || !item.name.trim() || item.name === '') {
                console.warn('Skipping item with invalid name:', item);
                continue;
            }
            
            // Skip items that look like they're from invalid S3 paths
            if (item.global_exists && !item.local_exists && item.downloadable && !item.s3_path) {
                console.warn('Skipping global item with missing s3_path:', item);
                continue;
            }
            
            const row = document.createElement('tr');
            row.dataset.path = item.path;
            row.dataset.globalModelPath = item.global_model_path || '';
            
            // Add special classes for global models
            if (item.global_exists && !item.local_exists) {
                row.classList.add('fs-global-model-available');
            } else if (item.global_exists && item.local_exists) {
                row.classList.add('fs-global-model-downloaded');
            }
            
            // Name column with improved structure
            const nameCell = document.createElement('td');
            nameCell.innerHTML = `
                <div class="fs-item">
                    ${this.getItemIcon(item)}
                    <div style="flex: 1; min-width: 0; display: flex; align-items: center; justify-content: space-between;">
                        ${this.getItemNameElement(item, onNavigateLinkClick, onGlobalModelDownload)}
                        ${this.getGlobalModelIndicator(item)}
                    </div>
                </div>
            `;
            
            // Type column
            const typeCell = document.createElement('td');
            typeCell.textContent = item.type;
            
            // Size column
            const sizeCell = document.createElement('td');
            sizeCell.textContent = item.type === 'file' ? this.formatFileSize(item.size) : '-';
            
            // Modified column
            const modifiedCell = document.createElement('td');
            modifiedCell.textContent = item.modified ? new Date(item.modified * 1000).toLocaleString() : '-';
            
            // Actions column
            const actionsCell = document.createElement('td');
            actionsCell.innerHTML = `
                <span class="fs-item-actions-trigger">⋮</span>
            `;
            
            // Event listeners
            row.addEventListener('click', (e) => onItemClick(item, e));
            
            const actionTrigger = actionsCell.querySelector('.fs-item-actions-trigger');
            actionTrigger.addEventListener('click', (e) => {
                e.stopPropagation();
                onActionTriggerClick(item, actionTrigger);
            });
            
            // Add download button event listener for global models
            if (item.global_exists && !item.local_exists && onGlobalModelDownload) {
                const downloadBtn = nameCell.querySelector('.fs-download-btn');
                if (downloadBtn) {
                    downloadBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        onGlobalModelDownload(item);
                    });
                }
            }
            
            row.appendChild(nameCell);
            row.appendChild(typeCell);
            row.appendChild(sizeCell);
            row.appendChild(modifiedCell);
            row.appendChild(actionsCell);
            
            tbody.appendChild(row);
        }
    }

    static getItemNameElement(item, onNavigateLinkClick, onGlobalModelDownload) {
        if (item.type === 'directory') {
            return `<a href="#" class="fs-item-name-link" data-path="${item.path}" style="flex: 1;">${item.name}</a>`;
        } else if (item.global_exists && !item.local_exists && item.downloadable) {
            // Use global_model_path if available, otherwise construct from path
            let modelPath = item.global_model_path;
            if (!modelPath && item.path) {
                // Extract model path from full path (remove 'models/' prefix)
                const pathParts = item.path.split('/');
                if (pathParts[0] === 'models' && pathParts.length > 1) {
                    modelPath = pathParts.slice(1).join('/');
                } else {
                    modelPath = item.path;
                }
            }
            
            // Ensure we have a valid model path
            if (!modelPath || modelPath.trim() === '') {
                console.warn('Invalid model path for global model:', item);
                return `<span class="fs-item-name" style="flex: 1;">${item.name}</span>`;
            }
            
            return `
                <div class="fs-global-model-name" style="flex: 1;">
                    <span class="fs-item-name">${item.name}</span>
                    <button class="fs-download-btn" data-model-path="${modelPath}" data-full-path="${item.path}" title="Download ${item.name} from global storage">
                        📥 Download
                    </button>
                </div>
            `;
        } else {
            return `<span class="fs-item-name" style="flex: 1;">${item.name}</span>`;
        }
    }

    static getGlobalModelIndicator(item) {
        if (item.global_exists && !item.local_exists && item.downloadable) {
            return '<span class="fs-global-indicator">🌐 Global</span>';
        } else if (item.global_exists && item.local_exists) {
            return '<span class="fs-global-indicator">✅ Synced</span>';
        } else if (item.global_exists && !item.local_exists && item.type === 'directory') {
            return '<span class="fs-global-indicator">🌐 Browse</span>';
        }
        return '';
    }

    static getItemIcon(item) {
        if (item.type === 'directory') {
            if (item.global_exists && !item.local_exists) {
                return '<p><span class="fs-item-icon">🌐📁</span></p>';
            } else if (item.global_exists && item.local_exists) {
                return '<p><span class="fs-item-icon">📁✅</span></p>';
            }
            return '<p><span class="fs-item-icon">📁</span></p>';
        } else {
            if (item.global_exists && !item.local_exists) {
                return '<p><span class="fs-item-icon">📄🌐</span></p>';
            }
            const extension = item.name.split('.').pop().toLowerCase();
            if (['safetensors', 'ckpt', 'pt', 'pth', 'bin'].includes(extension)) {
                return '<span class="fs-item-icon">🤖</span>';
            }
            return '<span class="fs-item-icon">📄</span>';
        }
    }

    static showGlobalModelProgress(modal, modelPath, progress) {
        const downloadBtn = modal.querySelector(`[data-model-path="${modelPath}"]`);
        if (!downloadBtn) return;
        
        const container = downloadBtn.closest('tr');
        if (!container) return;
        
        let progressContainer = container.querySelector('.fs-global-progress');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.className = 'fs-global-progress';
            progressContainer.innerHTML = `
                <div class="fs-global-progress-bar">
                    <div class="fs-global-progress-fill" style="width: 0%"></div>
                </div>
                <div class="fs-global-progress-text">Starting...</div>
                <button class="fs-global-cancel-btn" title="Cancel Download">×</button>
            `;
            
            const nameCell = downloadBtn.closest('.fs-item');
            nameCell.appendChild(progressContainer);
            downloadBtn.style.display = 'none';
        }
        
        const progressFill = progressContainer.querySelector('.fs-global-progress-fill');
        const progressText = progressContainer.querySelector('.fs-global-progress-text');
        const cancelBtn = progressContainer.querySelector('.fs-global-cancel-btn');
        
        // Update progress bar
        if (progressFill) {
            const percentage = Math.round(progress.progress || 0);
            progressFill.style.width = `${percentage}%`;
        }
        
        // Update progress text based on status
        if (progressText) {
            if (progress.status === 'downloading') {
                const downloaded = this.formatFileSize(progress.downloaded_size || 0);
                const total = progress.total_size ? this.formatFileSize(progress.total_size) : 'Unknown';
                const percentage = Math.round(progress.progress || 0);
                
                if (progress.total_size && progress.total_size > 0) {
                    progressText.textContent = `${downloaded} / ${total} (${percentage}%)`;
                } else {
                    progressText.textContent = `${downloaded} downloaded (${percentage}%)`;
                }
            } else if (progress.status === 'finishing') {
                progressText.textContent = 'Finishing download...';
            } else if (progress.status === 'failed') {
                progressText.textContent = `Failed: ${progress.error || 'Unknown error'}`;
                progressText.style.color = '#dc3545';
            } else if (progress.status === 'cancelled') {
                progressText.textContent = 'Download cancelled';
                progressText.style.color = '#ffc107';
            } else {
                progressText.textContent = progress.status || 'Processing...';
            }
        }
        
        // Handle cancel button
        if (cancelBtn && !cancelBtn.hasAttribute('data-listener-attached')) {
            cancelBtn.setAttribute('data-listener-attached', 'true');
            cancelBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const cancelEvent = new CustomEvent('globalModelCancel', {
                    detail: { modelPath: modelPath }
                });
                modal.dispatchEvent(cancelEvent);
            });
        }
        
        // Handle completion
        if (progress.status === 'downloaded') {
            progressText.textContent = 'Download complete!';
            progressText.style.color = '#28a745';
            cancelBtn.style.display = 'none';
            
            setTimeout(() => {
                progressContainer.remove();
                downloadBtn.style.display = 'inline-block';
                
                // Trigger refresh event
                const refreshEvent = new CustomEvent('globalModelDownloaded', {
                    detail: { modelPath: modelPath }
                });
                modal.dispatchEvent(refreshEvent);
            }, 2000);
        } else if (progress.status === 'failed' || progress.status === 'cancelled') {
            cancelBtn.style.display = 'none';
            
            // Add retry button for failed downloads
            if (progress.status === 'failed') {
                let retryBtn = progressContainer.querySelector('.fs-global-retry-btn');
                if (!retryBtn) {
                    retryBtn = document.createElement('button');
                    retryBtn.className = 'fs-global-retry-btn';
                    retryBtn.textContent = '🔄';
                    retryBtn.title = 'Retry Download';
                    retryBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        progressContainer.remove();
                        downloadBtn.style.display = 'inline-block';
                        downloadBtn.click();
                    });
                    progressContainer.appendChild(retryBtn);
                }
            }
        }
    }

    static hideGlobalModelProgress(modal, modelPath) {
        const downloadBtn = modal.querySelector(`[data-model-path="${modelPath}"]`);
        if (!downloadBtn) return;
        
        const container = downloadBtn.closest('tr');
        if (!container) return;
        
        const progressContainer = container.querySelector('.fs-global-progress');
        if (progressContainer) {
            progressContainer.remove();
        }
        
        downloadBtn.style.display = 'inline-block';
    }

    static updateActions(modal, hasSelectedItems) {
        const deleteBtn = modal.querySelector('#fs-delete');
        const downloadBtn = modal.querySelector('#fs-download-selected');
        
        deleteBtn.disabled = !hasSelectedItems;
        downloadBtn.disabled = !hasSelectedItems;
    }

    static updateItemCount(modal, count) {
        const itemCount = modal.querySelector('#fs-item-count');
        itemCount.textContent = `${count} item${count !== 1 ? 's' : ''}`;
    }

    static showMessage(modal, message, isError = false) {
        const messageDiv = modal.querySelector('#fs-message');
        messageDiv.className = `fs-message ${isError ? 'fs-error' : 'fs-success'}`;
        messageDiv.textContent = message;
        
        // Clear message after 5 seconds
        setTimeout(() => {
            if (messageDiv.textContent === message) {
                messageDiv.textContent = '';
                messageDiv.className = 'fs-message';
            }
        }, 5000);
    }

    static showStatus(modal, status) {
        const statusSpan = modal.querySelector('#fs-status');
        statusSpan.textContent = status;
    }

    static showCreateFolderForm(modal) {
        const form = modal.querySelector('#fs-create-folder-form');
        const input = modal.querySelector('#fs-folder-name');
        
        form.style.display = 'flex';
        input.value = '';
        input.focus();
    }

    static hideCreateFolderForm(modal) {
        const form = modal.querySelector('#fs-create-folder-form');
        form.style.display = 'none';
    }

    static showUploadOptions(modal) {
        const optionsView = modal.querySelector('#fs-upload-options');
        const formView = modal.querySelector('#fs-upload-form');
        const title = modal.querySelector('#fs-upload-title');
        const destinationInfo = modal.querySelector('#fs-upload-destination-info');
        
        optionsView.style.display = 'block';
        formView.style.display = 'none';
        title.textContent = 'Upload File';
        if(destinationInfo) destinationInfo.style.display = 'none';
    }

    static showUploadForm(modal, type, destinationPathForDisplay) {
        const optionsView = modal.querySelector('#fs-upload-options');
        const formView = modal.querySelector('#fs-upload-form');
        const title = modal.querySelector('#fs-upload-title');
        const urlInput = modal.querySelector('#fs-upload-url');
        const urlLabel = modal.querySelector('#fs-upload-url-label');
        const formTitle = modal.querySelector('#fs-upload-form-title');
        const typeSpecificFieldsContainer = modal.querySelector('#fs-upload-type-specific-fields');
        const destinationInfo = modal.querySelector('#fs-upload-destination-info');
        
        optionsView.style.display = 'none';
        formView.style.display = 'block';

        if (destinationInfo) {
            destinationInfo.textContent = `Upload to: ${destinationPathForDisplay || 'current directory'}`;
            destinationInfo.style.display = 'block';
        }
        
        // Update title and form based on type
        const typeConfig = {
            'google-drive': {
                title: 'Upload from Google Drive',
                urlPlaceholder: 'Enter Google Drive share link or File ID...',
                urlLabelText: 'Google Drive URL/File ID:',
                extraFieldsHTML: `
                    <div class="fs-form-group">
                        <label for="fs-gdrive-filename">Filename (without extension):</label>
                        <input type="text" id="fs-gdrive-filename" class="fs-form-input" placeholder="e.g., my_model">
                    </div>
                    <div class="fs-form-group">
                        <label for="fs-gdrive-extension">Extension:</label>
                        <input type="text" id="fs-gdrive-extension" class="fs-form-input" placeholder="e.g., safetensors, ckpt, zip">
                    </div>
                    <div class="fs-form-group fs-checkbox-form-group">
                        <div class="fs-checkbox-group">
                            <input type="checkbox" id="fs-gdrive-overwrite" style="width: auto;">
                            <label for="fs-gdrive-overwrite" style="margin-bottom: 0;">Overwrite existing file</label>
                        </div>
                    </div>
                    <div class="fs-form-group fs-checkbox-form-group">
                        <div class="fs-checkbox-group">
                            <input type="checkbox" id="fs-gdrive-auto-extract" checked style="width: auto;">
                            <label for="fs-gdrive-auto-extract" style="margin-bottom: 0;">Auto-extract zip files</label>
                        </div>
                    </div>
                `
            },
            'huggingface': {
                title: 'Upload from Hugging Face',
                urlPlaceholder: 'Enter Hugging Face Repo ID (e.g., user/repo) or File URL',
                urlLabelText: 'HF Repo ID / File URL:',
                extraFieldsHTML: `
                    <div class="fs-form-group fs-checkbox-form-group">
                        <div class="fs-checkbox-group">
                            <input type="checkbox" id="fs-hf-overwrite" style="width: auto;">
                            <label for="fs-hf-overwrite" style="margin-bottom: 0;">Overwrite existing files/folders</label>
                        </div>
                    </div>
                    <div class="fs-form-group" id="fs-hf-token-group" style="display: none;">
                        <label for="fs-hf-token">Your Hugging Face Token:</label>
                        <input type="password" id="fs-hf-token" class="fs-form-input" placeholder="hf_...">
                        <small style="color: var(--input-text); opacity: 0.7; font-size: 12px; margin-top: 4px; display: block;">
                            We don't store your token. It's only used for this download.
                        </small>
                    </div>
                `
            },
            'civitai': {
                title: 'Upload from Civitai',
                urlPlaceholder: 'Enter Civitai model ID, URL, or download link...',
                urlLabelText: 'Civitai Model ID/URL:',
                extraFieldsHTML: `
                    <div class="fs-form-group">
                        <label for="fs-civitai-filename">Custom Filename (optional):</label>
                        <input type="text" id="fs-civitai-filename" class="fs-form-input" placeholder="Leave empty to use original filename">
                    </div>
                    <div class="fs-form-group fs-checkbox-form-group">
                        <div class="fs-checkbox-group">
                            <input type="checkbox" id="fs-civitai-overwrite" style="width: auto;">
                            <label for="fs-civitai-overwrite" style="margin-bottom: 0;">Overwrite existing files</label>
                        </div>
                    </div>
                    <div class="fs-form-group" id="fs-civitai-token-group" style="display: none;">
                        <label for="fs-civitai-token">Your CivitAI API Token:</label>
                        <input type="password" id="fs-civitai-token" class="fs-form-input" placeholder="API token for private/restricted models">
                        <small style="color: var(--input-text); opacity: 0.7; font-size: 12px; margin-top: 4px; display: block;">
                            We don't store your token. It's only used for this download.
                        </small>
                    </div>
                `
            },
            'direct-link': {
                title: 'Upload from Direct Link',
                urlPlaceholder: 'Enter direct download URL...',
                urlLabelText: 'Direct Download URL:',
                extraFieldsHTML: `
                    <div class="fs-form-group">
                        <label for="fs-direct-filename">Custom Filename (optional):</label>
                        <input type="text" id="fs-direct-filename" class="fs-form-input" placeholder="Leave empty to auto-detect from URL">
                    </div>
                    <div class="fs-form-group fs-checkbox-form-group">
                        <div class="fs-checkbox-group">
                            <input type="checkbox" id="fs-direct-overwrite" style="width: auto;">
                            <label for="fs-direct-overwrite" style="margin-bottom: 0;">Overwrite existing files</label>
                        </div>
                    </div>
                `
            },
        };
        
        const config = typeConfig[type] || typeConfig['direct-link'];
        formTitle.textContent = config.title;
        urlInput.placeholder = config.urlPlaceholder;
        urlLabel.textContent = config.urlLabelText || 'URL:';
        typeSpecificFieldsContainer.innerHTML = config.extraFieldsHTML || '';
        
        // Clear previous values
        urlInput.value = '';
        // Clear common optional filename if it exists from other types
        const commonFilenameInput = modal.querySelector('#fs-upload-filename'); // This ID seems unused
        if (commonFilenameInput) commonFilenameInput.value = '';

        // Clear any previous progress/messages
        this.hideUploadProgress(modal);
        this.showUploadMessage(modal, '', false);

        // The FileSystemManager instance will handle attaching input listeners
        // and setting the initial button state after this method.
    }

    static showUploadProgress(modal, message, percentage) {
        const progressContainer = modal.querySelector('#fs-upload-progress');
        const textElement = modal.querySelector('.fs-upload-progress-text');
        const fillElement = modal.querySelector('.fs-upload-progress-fill');

        if (progressContainer && textElement && fillElement) {
            progressContainer.style.display = 'block';
            // Format the message to include the percentage
            let displayMessage = message;
            if (typeof percentage === 'number') {
                displayMessage = `${message} (${Math.round(percentage)}%)`;
            }
            textElement.textContent = displayMessage;
            fillElement.style.width = `${percentage}%`;
            
            // Add cancel button if it doesn't exist
            let cancelButton = progressContainer.querySelector('.fs-upload-cancel-btn');
            if (!cancelButton) {
                cancelButton = document.createElement('button');
                cancelButton.className = 'fs-upload-cancel-btn';
                cancelButton.innerHTML = '×';
                cancelButton.title = 'Cancel Download';
                cancelButton.addEventListener('click', () => {
                    // Trigger cancel event that FileSystemManager will listen to
                    const cancelEvent = new CustomEvent('uploadCancel');
                    modal.dispatchEvent(cancelEvent);
                });
                progressContainer.appendChild(cancelButton);
            }
        }
    }

    static hideUploadProgress(modal) {
        const progressContainer = modal.querySelector('#fs-upload-progress');
        if (progressContainer) {
            progressContainer.style.display = 'none';
            modal.querySelector('.fs-upload-progress-text').textContent = '';
            modal.querySelector('.fs-upload-progress-fill').style.width = '0%';
            
            // Remove cancel button
            const cancelButton = progressContainer.querySelector('.fs-upload-cancel-btn');
            if (cancelButton) {
                cancelButton.remove();
            }
        }
    }

    static showUploadMessage(modal, message, isError = false, allowHTML = false) {
        const messageDiv = modal.querySelector('#fs-upload-message');
        if (messageDiv) {
            if (allowHTML) {
                messageDiv.innerHTML = message;
            } else {
                messageDiv.textContent = message;
            }
            messageDiv.className = `fs-message ${isError ? 'fs-error' : 'fs-success'}`;
            if (!message) {
                messageDiv.className = 'fs-message'; // Clear classes if message is empty
                messageDiv.innerHTML = '';
            }
        }
    }

    static showHFTokenInput(modal, show = true) {
        const tokenGroup = modal.querySelector('#fs-hf-token-group');
        if (tokenGroup) {
            tokenGroup.style.display = show ? 'block' : 'none';
        }
    }

    static showCivitAITokenInput(modal, show = true) {
        const tokenGroup = modal.querySelector('#fs-civitai-token-group');
        if (tokenGroup) {
            tokenGroup.style.display = show ? 'block' : 'none';
        }
    }

    static createItemContextMenu(actions, onAction) {
        const menu = document.createElement('div');
        menu.className = 'fs-item-context-menu';
        
        actions.forEach(action => {
            const item = document.createElement('div');
            item.className = 'fs-item-context-menu-item';
            item.innerHTML = `
                <span>${action.icon}</span>
                <span>${action.label}</span>
            `;
            item.addEventListener('click', () => onAction(action.id));
            menu.appendChild(item);
        });
        
        return menu;
    }

    static updateSelection(modal, selectedItems) {
        const rows = modal.querySelectorAll('#fs-table-body tr');
        rows.forEach(row => {
            const path = row.dataset.path;
            if (selectedItems.has(path)) {
                row.classList.add('fs-item-selected');
            } else {
                row.classList.remove('fs-item-selected');
            }
        });
    }

    static formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}