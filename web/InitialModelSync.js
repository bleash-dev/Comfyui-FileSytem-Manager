/**
 * Initial Models Sync Dialog
 * Displays when pod starts and there are models to sync from S3
 */

export class InitialModelsSyncDialog {
    constructor() {
        this.isVisible = false;
        this.models = {};
        this.selectedModels = new Set();
        this.syncInProgress = false;
        this.progressInterval = null;
        this.lastProgressUpdate = null;
        this.progressHistory = [];
        
        this.injectStyles();
        this.createElement();
        this.bindEvents();
    }

    injectStyles() {
        // Inject CSS for animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.7; }
                100% { opacity: 1; }
            }
            
            .initial-sync-dialog .status-badge {
                transition: all 0.3s ease;
            }
            
            .initial-sync-dialog .model-progress-fill {
                background: linear-gradient(90deg, #007bff, #0056b3);
                background-size: 200% 100%;
                animation: progress-shimmer 2s infinite linear;
            }
            
            @keyframes progress-shimmer {
                0% { background-position: 200% 0; }
                100% { background-position: -200% 0; }
            }
        `;
        document.head.appendChild(style);
    }

    createElement() {
        // Create dialog overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'initial-sync-overlay';
        this.overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 10000;
            display: none;
            justify-content: center;
            align-items: center;
        `;

        // Create dialog content
        this.dialog = document.createElement('div');
        this.dialog.className = 'initial-sync-dialog';
        this.dialog.style.cssText = `
            background: var(--comfy-menu-bg);
            border: 2px solid var(--border-color);
            border-radius: 8px;
            padding: 24px;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            color: var(--fg-color);
            font-family: monospace;
        `;

        this.dialog.innerHTML = `
            <div class="sync-header">
                <h2 style="margin: 0 0 16px 0; color: var(--fg-color);">
                    🔄 Sync Your Models from the cloud ☁️
                </h2>
                <p style="margin: 0 0 20px 0; color: var(--descrip-text);">
                    These are the models you had on this instance before you left
                </p>
            </div>

            <div class="sync-summary" style="margin-bottom: 20px;">
                <div class="summary-stats" style="
                    display: flex;
                    gap: 20px;
                    margin-bottom: 16px;
                    padding: 12px;
                    background: var(--comfy-input-bg);
                    border-radius: 4px;
                ">
                    <span class="total-models">Models: <strong>0</strong></span>
                    <span class="total-size">Total Size: <strong>0 B</strong></span>
                    <span class="selected-count">Selected: <strong>0</strong></span>
                </div>
                
                <div class="selection-controls" style="margin-bottom: 16px;">
                    <button class="select-all-btn" style="
                        background: var(--comfy-input-bg);
                        border: 1px solid var(--border-color);
                        color: var(--fg-color);
                        padding: 6px 12px;
                        border-radius: 4px;
                        cursor: pointer;
                        margin-right: 8px;
                    ">Select All</button>
                    <button class="select-none-btn" style="
                        background: var(--comfy-input-bg);
                        border: 1px solid var(--border-color);
                        color: var(--fg-color);
                        padding: 6px 12px;
                        border-radius: 4px;
                        cursor: pointer;
                    ">Select None</button>
                </div>
            </div>

            <div class="models-list" style="
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid var(--border-color);
                border-radius: 4px;
                margin-bottom: 20px;
            "></div>

            <div class="sync-progress" style="display: none; margin-bottom: 20px;">
                <div class="progress-header" style="
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 8px;
                ">
                    <span>Download Progress</span>
                    <span class="progress-text">0%</span>
                </div>
                <div class="progress-bar" style="
                    width: 100%;
                    height: 20px;
                    background: var(--comfy-input-bg);
                    border-radius: 10px;
                    overflow: hidden;
                ">
                    <div class="progress-fill" style="
                        height: 100%;
                        background: linear-gradient(90deg, #4CAF50, #45a049);
                        width: 0%;
                        transition: width 0.3s ease;
                    "></div>
                </div>
                <div class="progress-details" style="
                    margin-top: 8px;
                    font-size: 12px;
                    color: var(--descrip-text);
                "></div>
                <div class="queue-status" style="
                    margin-top: 12px;
                    padding: 8px;
                    background: var(--comfy-input-bg);
                    border-radius: 4px;
                    font-size: 11px;
                    border-left: 3px solid #007bff;
                ">
                    <div class="queue-summary" style="font-weight: bold; margin-bottom: 4px;">
                        Queue Status
                    </div>
                    <div class="queue-details" style="color: var(--descrip-text);">
                        Preparing downloads...
                    </div>
                </div>
            </div>

            <div class="sync-actions" style="
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            ">
                <button class="skip-btn" style="
                    background: var(--comfy-input-bg);
                    border: 1px solid var(--border-color);
                    color: var(--fg-color);
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                ">Skip for Now</button>
                <button class="sync-btn" style="
                    background: #007bff;
                    border: 1px solid #0056b3;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                " disabled>Sync Selected Models</button>
                <--<button class="cancel-btn" style="
                    background: #dc3545;
                    border: 1px solid #c82333;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                    display: none;
                ">Cancel Download</button> -->
                <button class="retry-failed-btn" style="
                    background: #fd7e14;
                    border: 1px solid #e85e00;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 4px;
                    cursor: pointer;
                    display: none;
                ">Retry Failed</button>
            </div>
        `;

        this.overlay.appendChild(this.dialog);
        document.body.appendChild(this.overlay);

        // Get element references
        this.modelsList = this.dialog.querySelector('.models-list');
        this.summaryStats = this.dialog.querySelector('.summary-stats');
        this.syncProgress = this.dialog.querySelector('.sync-progress');
        this.progressFill = this.dialog.querySelector('.progress-fill');
        this.progressText = this.dialog.querySelector('.progress-text');
        this.progressDetails = this.dialog.querySelector('.progress-details');
        this.queueStatus = this.dialog.querySelector('.queue-status');
        this.queueDetails = this.dialog.querySelector('.queue-details');
        
        this.selectAllBtn = this.dialog.querySelector('.select-all-btn');
        this.selectNoneBtn = this.dialog.querySelector('.select-none-btn');
        this.skipBtn = this.dialog.querySelector('.skip-btn');
        this.syncBtn = this.dialog.querySelector('.sync-btn');
        // this.cancelBtn = this.dialog.querySelector('.cancel-btn');
        this.retryFailedBtn = this.dialog.querySelector('.retry-failed-btn');
    }

    bindEvents() {
        this.selectAllBtn.addEventListener('click', () => this.selectAll());
        this.selectNoneBtn.addEventListener('click', () => this.selectNone());
        this.skipBtn.addEventListener('click', () => this.skipSync());
        this.syncBtn.addEventListener('click', () => this.startSync());
        // this.cancelBtn.addEventListener('click', () => this.cancelSync());
        this.retryFailedBtn.addEventListener('click', () => this.retryFailedDownloads());
    }

    async checkAndShow() {
        try {
            // Check if we should show the dialog and get models in one call
            const response = await fetch('/filesystem/initial_sync/should_show');
            const data = await response.json();

            if (data.error) {
                console.error('Failed to check initial sync status:', data.error);
                return false;
            }

            if (!data.shouldShow) {
                console.log('Initial sync not needed:', data.reason);
                return false;
            }

            // Models data is already included in the response
            if (!data.models || data.totalModels === 0) {
                // No models to sync, mark as completed
                await this.markSyncCompleted();
                return false;
            }

            this.models = data.models.models;
            this.updateUI(data.models);
            this.show();
            return true;

        } catch (error) {
            console.error('Error checking initial sync:', error);
            return false;
        }
    }

    updateUI(data) {
        // Update summary statistics
        this.summaryStats.innerHTML = `
            <span class="total-models">Models: <strong>${data.totalModels}</strong></span>
            <span class="total-size">Total Size: <strong>${data.formattedSize}</strong></span>
            <span class="selected-count">Selected: <strong>0</strong></span>
        `;

        // Populate models list
        this.modelsList.innerHTML = '';
        Object.entries(this.models).forEach(([groupName, groupModels]) => {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'model-group';
            groupDiv.style.cssText = `
                margin-bottom: 16px;
                border: 1px solid var(--border-color);
                border-radius: 4px;
                overflow: hidden;
            `;

            const groupHeader = document.createElement('div');
            groupHeader.style.cssText = `
                background: var(--comfy-input-bg);
                padding: 12px;
                font-weight: bold;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                justify-content: space-between;
                align-items: center;
            `;
            groupHeader.innerHTML = `
                <span>${groupName}</span>
                <span style="font-size: 12px; color: var(--descrip-text);">
                    ${Object.keys(groupModels).length} models
                </span>
            `;

            const modelsContainer = document.createElement('div');
            modelsContainer.style.padding = '8px';

            Object.entries(groupModels).forEach(([modelName, modelData]) => {
                const modelDiv = document.createElement('div');
                modelDiv.className = 'model-item';
                modelDiv.style.cssText = `
                    display: flex;
                    align-items: center;
                    padding: 8px;
                    border-radius: 4px;
                    margin-bottom: 4px;
                    background: var(--comfy-menu-bg);
                `;

                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'model-checkbox';
                checkbox.dataset.group = groupName;
                checkbox.dataset.model = modelName;
                checkbox.dataset.modelKey = `${groupName}:::${modelName}`;
                checkbox.style.marginRight = '12px';

                const modelInfo = document.createElement('div');
                modelInfo.style.flex = '1';
                modelInfo.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 4px;">${modelName}</div>
                    <div style="font-size: 12px; color: var(--descrip-text);">
                        Size: ${this.formatFileSize(modelData.modelSize)} • 
                        Path: ${modelData.localPath}
                    </div>
                    <div class="model-status" style="
                        font-size: 11px; 
                        margin-top: 4px;
                        display: none;
                        transition: all 0.3s ease;
                    ">
                        <span class="status-badge" style="
                            padding: 2px 6px;
                            border-radius: 3px;
                            font-weight: bold;
                            text-transform: uppercase;
                            transition: all 0.3s ease;
                        ">Pending</span>
                        <div class="model-progress" style="
                            margin-top: 4px;
                            display: none;
                            transition: all 0.3s ease;
                        ">
                            <div class="model-progress-bar" style="
                                width: 100%;
                                height: 4px;
                                background: var(--comfy-input-bg);
                                border-radius: 2px;
                                overflow: hidden;
                            ">
                                <div class="model-progress-fill" style="
                                    height: 100%;
                                    background: linear-gradient(90deg, #007bff, #0056b3);
                                    width: 0%;
                                    transition: width 0.5s ease;
                                "></div>
                            </div>
                            <div class="model-progress-text" style="
                                font-size: 10px;
                                margin-top: 2px;
                                color: var(--descrip-text);
                            "></div>
                        </div>
                    </div>
                `;

                const removeBtn = document.createElement('button');
                removeBtn.textContent = 'Remove';
                removeBtn.className = 'remove-model-btn';
                removeBtn.style.cssText = `
                    background: #dc3545;
                    border: 1px solid #c82333;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                `;
                removeBtn.onclick = () => this.removeModel(groupName, modelName, modelData.localPath);

                checkbox.addEventListener('change', () => this.updateSelection());

                modelDiv.appendChild(checkbox);
                modelDiv.appendChild(modelInfo);
                modelDiv.appendChild(removeBtn);
                modelsContainer.appendChild(modelDiv);
            });

            groupDiv.appendChild(groupHeader);
            groupDiv.appendChild(modelsContainer);
            this.modelsList.appendChild(groupDiv);
        });

        this.updateSyncButtonState();
    }

    updateSelection() {
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox');
        const selectedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        
        // Update selected count display
        const selectedCountSpan = this.summaryStats.querySelector('.selected-count strong');
        selectedCountSpan.textContent = selectedCount;

        this.updateSyncButtonState();
    }

    updateSyncButtonState() {
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox');
        const hasSelected = Array.from(checkboxes).some(cb => cb.checked);
        
        this.syncBtn.disabled = !hasSelected || this.syncInProgress;
        this.syncBtn.style.opacity = this.syncBtn.disabled ? '0.5' : '1';
    }

    selectAll() {
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox');
        checkboxes.forEach(cb => cb.checked = true);
        this.updateSelection();
    }

    selectNone() {
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox');
        checkboxes.forEach(cb => cb.checked = false);
        this.updateSelection();
    }

    async removeModel(groupName, modelName, localPath) {
        if (!confirm(`Are you sure you want to remove "${modelName}" from your configuration?`)) {
            return;
        }

        try {
            const response = await fetch('/filesystem/initial_sync/remove_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_path: localPath })
            });

            const data = await response.json();
            if (data.success) {
                // Remove from UI
                delete this.models[groupName][modelName];
                if (Object.keys(this.models[groupName]).length === 0) {
                    delete this.models[groupName];
                }

                // Refresh UI
                const totalModels = Object.values(this.models).reduce((sum, group) => sum + Object.keys(group).length, 0);
                const totalSize = Object.values(this.models).reduce((sum, group) => 
                    sum + Object.values(group).reduce((groupSum, model) => groupSum + (model.modelSize || 0), 0), 0);

                this.updateUI({
                    totalModels,
                    formattedSize: this.formatFileSize(totalSize)
                });

                // Check if no models left
                if (totalModels === 0) {
                    this.hide();
                }
            } else {
                alert(`Failed to remove model: ${data.error}`);
            }
        } catch (error) {
            console.error('Error removing model:', error);
            alert('Failed to remove model. Please try again.');
        }
    }

    async startSync() {
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox:checked');
        const selectedModels = [];

        checkboxes.forEach(cb => {
            const groupName = cb.dataset.group;
            const modelName = cb.dataset.model;
            const modelData = this.models[groupName][modelName];
            selectedModels.push(modelData);
        });

        if (selectedModels.length === 0) {
            alert('Please select at least one model to sync.');
            return;
        }

        try {
            this.syncInProgress = true;
            this.updateSyncButtonState();
            this.showProgress();

            // Show initial status for all selected models
            this.showInitialModelStatuses();

            const response = await fetch('/filesystem/initial_sync/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models: selectedModels })
            });

            const data = await response.json();
            if (data.success) {
                this.startProgressMonitoring();
            } else {
                throw new Error(data.error || 'Failed to start sync');
            }

        } catch (error) {
            console.error('Error starting sync:', error);
            alert(`Failed to start sync: ${error.message}`);
            this.syncInProgress = false;
            this.updateSyncButtonState();
            this.hideProgress();
        }
    }

    showInitialModelStatuses() {
        // Show initial "queued" status for all selected models
        const checkboxes = this.modelsList.querySelectorAll('.model-checkbox:checked');
        
        checkboxes.forEach(checkbox => {
            const modelDiv = checkbox.closest('.model-item');
            const statusDiv = modelDiv.querySelector('.model-status');
            const statusBadge = modelDiv.querySelector('.status-badge');
            const progressDiv = modelDiv.querySelector('.model-progress');
            
            // Show status and set to queued
            statusDiv.style.display = 'block';
            this.updateStatusBadge(statusBadge, 'queued');
            progressDiv.style.display = 'none';
        });
    }

    showProgress() {
        this.syncProgress.style.display = 'block';
        this.skipBtn.style.display = 'none';
        this.syncBtn.style.display = 'none';
        // this.cancelBtn.style.display = 'inline-block';
    }

    hideProgress() {
        this.syncProgress.style.display = 'none';
        this.skipBtn.style.display = 'inline-block';
        this.syncBtn.style.display = 'inline-block';
        // this.cancelBtn.style.display = 'none';
    }

    startProgressMonitoring() {
        this.progressInterval = setInterval(async () => {
            try {
                const response = await fetch('/filesystem/initial_sync/progress');
                const data = await response.json();

                if (data.success && data.summary) {
                    const { summary, progress } = data;
                    const overallProgress = summary.overallProgress || 0;
                    
                    // Update overall progress
                    this.progressFill.style.width = `${overallProgress}%`;
                    this.progressText.textContent = `${overallProgress.toFixed(1)}%`;
                    
                    // Calculate speed and ETA
                    const now = Date.now();
                    if (this.lastProgressUpdate) {
                        const timeElapsed = (now - this.lastProgressUpdate.time) / 1000; // seconds
                        const bytesDownloaded = summary.downloadedSize - (this.lastProgressUpdate.downloadedSize || 0);
                        
                        if (timeElapsed > 0) {
                            const speed = bytesDownloaded / timeElapsed; // bytes per second
                            this.progressHistory.push({ time: now, speed, downloadedSize: summary.downloadedSize });
                            
                            // Keep only last 10 measurements for smoothing
                            if (this.progressHistory.length > 10) {
                                this.progressHistory.shift();
                            }
                            
                            // Calculate average speed
                            const avgSpeed = this.progressHistory.reduce((sum, p) => sum + p.speed, 0) / this.progressHistory.length;
                            const remainingBytes = summary.totalSize - summary.downloadedSize;
                            const eta = remainingBytes > 0 && avgSpeed > 0 ? remainingBytes / avgSpeed : 0;
                            
                            let etaText = '';
                            if (eta > 0 && eta < 86400) { // Less than 24 hours
                                const hours = Math.floor(eta / 3600);
                                const minutes = Math.floor((eta % 3600) / 60);
                                const seconds = Math.floor(eta % 60);
                                
                                if (hours > 0) etaText = ` • ETA: ${hours}h ${minutes}m`;
                                else if (minutes > 0) etaText = ` • ETA: ${minutes}m ${seconds}s`;
                                else etaText = ` • ETA: ${seconds}s`;
                            }
                            
                            this.progressDetails.textContent = 
                                `${summary.completedModels}/${summary.totalModels} models • ` +
                                `${summary.formattedDownloadedSize}/${summary.formattedTotalSize}` +
                                (avgSpeed > 0 ? ` • ${this.formatFileSize(avgSpeed)}/s` : '') +
                                etaText;
                        }
                    }
                    
                    this.lastProgressUpdate = {
                        time: now,
                        downloadedSize: summary.downloadedSize,
                        overallProgress
                    };

                    // Update individual model statuses
                    this.updateModelStatuses(progress);
                    
                    // Update queue status
                    this.updateQueueStatus(progress, summary);

                    // Check if completed
                    if (summary.completedModels === summary.totalModels) {
                        this.completeSync();
                    }
                }
            } catch (error) {
                console.error('Error getting sync progress:', error);
            }
        }, 1000);
    }

    updateQueueStatus(progressData, summary) {
        if (!progressData || Object.keys(progressData).length === 0) {
            this.queueDetails.textContent = 'Preparing downloads...';
            return;
        }

        console.log('Updating queue status with progress data:', progressData);
        console.log('Summary data:', summary);

        let queuedCount = 0;
        let downloadingCount = 0;
        let completedCount = 0;
        let failedCount = 0;
        let cancelledCount = 0;
        let currentlyDownloading = [];

        // Count models by status and track currently downloading
        Object.entries(progressData).forEach(([groupName, group]) => {
            Object.entries(group).forEach(([modelName, model]) => {
                const status = model.status || 'queued';
                
                // Map API status values to UI status values
                let uiStatus = status;
                if (status === 'progress') {
                    uiStatus = 'downloading';
                } else if (status === 'downloaded') {
                    uiStatus = 'completed';
                }
                
                console.log(`Model ${modelName}: API status=${status}, UI status=${uiStatus}`);
                
                switch (uiStatus) {
                    case 'queued':
                    case 'pending':
                        queuedCount++;
                        break;
                    case 'downloading':
                        downloadingCount++;
                        if (currentlyDownloading.length < 3) { // Show up to 3 model names
                            // Use the model name from the key or fallback to model data
                            const displayName = modelName || model.modelName || `Model ${downloadingCount}`;
                            currentlyDownloading.push(displayName);
                        }
                        break;
                    case 'completed':
                        completedCount++;
                        break;
                    case 'failed':
                        failedCount++;
                        break;
                    case 'cancelled':
                        cancelledCount++;
                        break;
                }
            });
        });

        // Build status text
        console.log(`Status counts: downloading=${downloadingCount}, queued=${queuedCount}, completed=${completedCount}, failed=${failedCount}, cancelled=${cancelledCount}`);
        
        const statusParts = [];
        if (downloadingCount > 0) {
            const downloadingText = downloadingCount === 1 ? 
                `Downloading: ${currentlyDownloading[0] || 'model'}` :
                `Downloading ${downloadingCount} models`;
            statusParts.push(downloadingText);
        }
        if (queuedCount > 0) statusParts.push(`${queuedCount} queued`);
        if (completedCount > 0) statusParts.push(`${completedCount} completed`);
        if (failedCount > 0) statusParts.push(`${failedCount} failed`);
        if (cancelledCount > 0) statusParts.push(`${cancelledCount} cancelled`);

        if (statusParts.length > 0) {
            this.queueDetails.innerHTML = statusParts.join(' • ');
            console.log('Queue status updated to:', statusParts.join(' • '));
        } else {
            this.queueDetails.textContent = 'No active downloads';
            console.log('Queue status: No active downloads');
        }

        // Update queue status color based on activity
        if (downloadingCount > 0) {
            this.queueStatus.style.borderLeftColor = '#007bff';
        } else if (failedCount > 0) {
            this.queueStatus.style.borderLeftColor = '#dc3545';
        } else if (completedCount > 0) {
            this.queueStatus.style.borderLeftColor = '#28a745';
        } else {
            this.queueStatus.style.borderLeftColor = '#fd7e14';
        }
    }

    updateModelStatuses(progressData) {
        if (!progressData) return;

        // Find all model divs and update their status
        const modelDivs = this.modelsList.querySelectorAll('.model-item');
        
        modelDivs.forEach(modelDiv => {
            const checkbox = modelDiv.querySelector('.model-checkbox');
            if (!checkbox || !checkbox.checked) return; // Only update selected models
            
            const modelKey = checkbox.dataset.modelKey;
            const [groupName, modelName] = modelKey.split(':::');
            
            // Find progress data for this model
            let modelProgress = null;
            if (progressData[groupName] && progressData[groupName][modelName]) {
                modelProgress = progressData[groupName][modelName];
            }
            
            const statusDiv = modelDiv.querySelector('.model-status');
            const statusBadge = modelDiv.querySelector('.status-badge');
            const progressDiv = modelDiv.querySelector('.model-progress');
            const progressFill = modelDiv.querySelector('.model-progress-fill');
            const progressText = modelDiv.querySelector('.model-progress-text');
            
            if (modelProgress) {
                // Show status div
                statusDiv.style.display = 'block';
                
                const status = modelProgress.status || 'pending';
                
                // Map API status values to UI status values
                let uiStatus = status;
                if (status === 'progress') {
                    uiStatus = 'downloading';
                } else if (status === 'downloaded') {
                    uiStatus = 'completed';
                }
                
                // Get progress data - handle different field names from API
                const downloadedBytes = modelProgress.downloaded || modelProgress.downloadedBytes || 0;
                const totalBytes = modelProgress.totalSize || modelProgress.totalBytes || 0;
                const progress = totalBytes > 0 ? (downloadedBytes / totalBytes) * 100 : 0;
                
                // Update status badge with UI status
                this.updateStatusBadge(statusBadge, uiStatus);
                
                // Show/hide progress bar based on status
                if (uiStatus === 'downloading' || uiStatus === 'completed') {
                    progressDiv.style.display = 'block';
                    progressFill.style.width = `${progress}%`;
                    
                    if (uiStatus === 'downloading') {
                        progressText.textContent = `${this.formatFileSize(downloadedBytes)} / ${this.formatFileSize(totalBytes)} (${progress.toFixed(1)}%)`;
                    } else if (uiStatus === 'completed') {
                        progressText.textContent = `✓ Complete (${this.formatFileSize(totalBytes)})`;
                    }
                } else {
                    progressDiv.style.display = 'none';
                }
            } else {
                // Model not in progress data - check if it should show as queued
                const isSelected = checkbox.checked;
                if (isSelected && this.syncInProgress) {
                    statusDiv.style.display = 'block';
                    this.updateStatusBadge(statusBadge, 'queued');
                    progressDiv.style.display = 'none';
                }
            }
        });
    }

    updateStatusBadge(badge, status) {
        const statusConfig = {
            'pending': { text: 'Pending', color: '#6c757d', bg: '#f8f9fa', border: '#6c757d' },
            'queued': { text: 'Queued', color: '#fd7e14', bg: '#fff3cd', border: '#fd7e14' },
            'downloading': { text: 'Downloading', color: '#007bff', bg: '#d1ecf1', border: '#007bff' },
            'completed': { text: '✓ Complete', color: '#28a745', bg: '#d4edda', border: '#28a745' },
            'failed': { text: '✗ Failed', color: '#dc3545', bg: '#f8d7da', border: '#dc3545' },
            'cancelled': { text: 'Cancelled', color: '#6c757d', bg: '#e2e3e5', border: '#6c757d' }
        };
        
        const config = statusConfig[status] || statusConfig['pending'];
        badge.textContent = config.text;
        badge.style.color = config.color;
        badge.style.backgroundColor = config.bg;
        badge.style.border = `1px solid ${config.border}`;
        
        // Add pulsing animation for downloading status
        if (status === 'downloading') {
            badge.style.animation = 'pulse 2s infinite';
            badge.style.transform = 'scale(1.02)';
        } else {
            badge.style.animation = 'none';
            badge.style.transform = 'scale(1)';
        }
    }

    async cancelSync() {
        if (!confirm('Are you sure you want to cancel the download?')) {
            return;
        }

        try {
            const response = await fetch('/filesystem/initial_sync/cancel', {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                this.completeSync(false);
            } else {
                alert(`Failed to cancel sync: ${data.error}`);
            }
        } catch (error) {
            console.error('Error cancelling sync:', error);
            alert('Failed to cancel sync. Please try again.');
        }
    }

    completeSync(success = true) {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }

        this.syncInProgress = false;
        
        // Update UI state
        this.updateSyncButtonState();
        this.hideProgress();
        
        // Hide all model statuses when sync is complete
        const modelStatuses = this.modelsList.querySelectorAll('.model-status');
        modelStatuses.forEach(status => {
            status.style.display = 'none';
        });
        
        if (success) {
            // Check for any failed downloads and show summary
            setTimeout(async () => {
                const failedModels = this.getFailedModels();
                let message = 'Models sync completed successfully!';
                
                if (failedModels.length > 0) {
                    message = `Sync completed with ${failedModels.length} failed downloads:\n\n` +
                             failedModels.map(model => `• ${model}`).join('\n') +
                             '\n\nWould you like to retry the failed downloads?';
                    
                    // Show retry button
                    this.retryFailedBtn.style.display = 'inline-block';
                    this.skipBtn.style.display = 'inline-block';
                    this.skipBtn.textContent = 'Skip Failed';
                    
                    alert(message);
                } else {
                    alert(message);
                    await this.markSyncCompleted();
                    this.hide();
                }
            }, 500);
        } else {
            // Sync was cancelled
            alert('Sync was cancelled.');
        }
    }

    getFailedModels() {
        const failedModels = [];
        const modelStatuses = this.modelsList.querySelectorAll('.model-status');
        
        modelStatuses.forEach(statusDiv => {
            const badge = statusDiv.querySelector('.status-badge');
            if (badge && badge.textContent.includes('Failed')) {
                const modelDiv = statusDiv.closest('.model-item');
                const modelNameDiv = modelDiv.querySelector('div[style*="font-weight: bold"]');
                if (modelNameDiv) {
                    failedModels.push(modelNameDiv.textContent);
                }
            }
        });
        
        return failedModels;
    }

    async skipSync() {
        if (confirm('Are you sure you want to skip syncing models? You can sync them later from the file manager.')) {
            await this.markSyncCompleted();
            this.hide();
        }
    }

    async retryFailedDownloads() {
        const failedModels = [];
        const modelDivs = this.modelsList.querySelectorAll('.model-item');
        
        // Find all failed models and prepare them for retry
        modelDivs.forEach(modelDiv => {
            const statusDiv = modelDiv.querySelector('.model-status');
            const badge = statusDiv?.querySelector('.status-badge');
            
            if (badge && badge.textContent.includes('Failed')) {
                const checkbox = modelDiv.querySelector('.model-checkbox');
                const groupName = checkbox.dataset.group;
                const modelName = checkbox.dataset.model;
                const modelData = this.models[groupName][modelName];
                
                if (modelData) {
                    failedModels.push(modelData);
                    // Reset status to queued
                    this.updateStatusBadge(badge, 'queued');
                    statusDiv.querySelector('.model-progress').style.display = 'none';
                }
            }
        });

        if (failedModels.length === 0) {
            alert('No failed downloads to retry.');
            return;
        }

        try {
            // Hide retry button and show progress again
            this.retryFailedBtn.style.display = 'none';
            this.skipBtn.textContent = 'Skip for Now';
            this.syncInProgress = true;
            this.showProgress();

            // Start downloading failed models
            const response = await fetch('/filesystem/initial_sync/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ models: failedModels })
            });

            const data = await response.json();
            if (data.success) {
                this.startProgressMonitoring();
            } else {
                throw new Error(data.error || 'Failed to start retry');
            }

        } catch (error) {
            console.error('Error retrying failed downloads:', error);
            alert(`Failed to retry downloads: ${error.message}`);
            this.syncInProgress = false;
            this.updateSyncButtonState();
            this.hideProgress();
        }
    }

    async markSyncCompleted() {
        try {
            await fetch('/filesystem/initial_sync/mark_completed', {
                method: 'POST'
            });
        } catch (error) {
            console.error('Error marking sync as completed:', error);
        }
    }

    show() {
        this.isVisible = true;
        this.overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    hide() {
        this.isVisible = false;
        this.overlay.style.display = 'none';
        document.body.style.overflow = '';
        
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

// Initialize dialog when DOM is ready
let initialSyncDialog = null;

export function initializeInitialSync() {
    if (!initialSyncDialog) {
        initialSyncDialog = new InitialModelsSyncDialog();
    }
    
    // Check and show dialog after a short delay to ensure ComfyUI is loaded
    setTimeout(() => {
        initialSyncDialog.checkAndShow();
    }, 2000);
}

// Auto-initialize when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeInitialSync);
} else {
    initializeInitialSync();
}

// Make available globally for debugging
window.InitialModelsSyncDialog = InitialModelsSyncDialog;
window.initializeInitialSync = initializeInitialSync;
