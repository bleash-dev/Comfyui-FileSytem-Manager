export class MissingModelUI {
    constructor() {
        this.addCustomStyles();
    }

    createCustomDialog(missingModels) {
        const dialog = document.createElement('div');
        dialog.className = 'p-dialog p-component global-dialog install-missing-models-dialog';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 1001;
            max-width: 700px;
            width: 90vw;
            max-height: 80vh;
            background: var(--comfy-menu-bg, #353535);
            border: 1px solid var(--border-color, #666);
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            pointer-events: auto;
        `;
        
        dialog.innerHTML = `
            <div class="p-dialog-header" data-pc-section="header">
                <h3>🔧 Missing Model Detected</h3>
                <div class="p-dialog-header-actions">
                    <button class="close-btn p-button p-component p-button-icon-only p-button-secondary" aria-label="Close">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg" class="p-icon p-button-icon">
                            <path d="M8.01186 7.00933L12.27 2.75116C12.341 2.68501 12.398 2.60524 12.4375 2.51661C12.4769 2.42798 12.4982 2.3323 12.4999 2.23529C12.5016 2.13827 12.4838 2.0419 12.4474 1.95194C12.4111 1.86197 12.357 1.78024 12.2884 1.71163C12.2198 1.64302 12.138 1.58893 12.0481 1.55259C11.9581 1.51625 11.8617 1.4984 11.7647 1.50011C11.6677 1.50182 11.572 1.52306 11.4834 1.56255C11.3948 1.60204 11.315 1.65898 11.2488 1.72997L6.99067 5.98814L2.7325 1.72997C2.59553 1.60234 2.41437 1.53286 2.22718 1.53616C2.03999 1.53946 1.8614 1.61529 1.72901 1.74767C1.59663 1.88006 1.5208 2.05865 1.5175 2.24584C1.5142 2.43303 1.58368 2.61419 1.71131 2.75116L5.96948 7.00933L1.71131 11.2675C1.576 11.403 1.5 11.5866 1.5 11.7781C1.5 11.9696 1.576 12.1532 1.71131 12.2887C1.84679 12.424 2.03043 12.5 2.2219 12.5C2.41338 12.5 2.59702 12.424 2.7325 12.2887L6.99067 8.03052L11.2488 12.2887C11.3843 12.424 11.568 12.5 11.7594 12.5C11.9509 12.5 12.1346 12.424 12.27 12.2887C12.4053 12.1532 12.4813 11.9696 12.4813 11.7781C12.4813 11.5866 12.4053 11.403 12.27 11.2675L8.01186 7.00933Z" fill="currentColor"></path>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="p-dialog-content" data-pc-section="content">
                <div class="install-missing-models-content">
                    <div class="error-explanation">
                        <div class="error-icon">
                            <i class="pi pi-exclamation-triangle" style="font-size: 2rem; color: #ffc107;"></i>
                        </div>
                        <div class="error-text">
                            <h4>Workflow execution failed due to missing model${missingModels.length > 1 ? 's' : ''}</h4>
                            <p>
                            We'll automatically search and download the required model${missingModels.length > 1 ? 's' : ''} From Community Repo, If it's not there, we will attempt from the internet (Hugging Face and CivitAI)
                            If not available, you can <span class="manual-installation-span">install manually</span> directly in your directory of choice while installing from multiple sources.
                            </p>
                        </div>
                    </div>
                    
                    <div class="missing-models-list">
                        ${missingModels.map((model, index) => `
                            <div class="missing-model-item" data-model-index="${index}">
                                <div class="model-info">
                                    <div class="model-name">${model.name}</div>
                                    <div class="model-details">
                                        <span class="model-category">${model.category}</span>
                                        <span class="model-field">Field: ${model.fieldName}</span>
                                        <span class="model-context">${model.errorContext}</span>
                                    </div>
                                </div>
                                <div class="model-actions">
                                    <button class="download-btn" data-model-index="${index}">
                                        📥 Download
                                    </button>
                                </div>
                                <div class="model-progress" style="display: none;">
                                    <div class="progress-info">
                                        <div class="progress-text">Preparing...</div>
                                        <button class="cancel-btn" data-model-index="${index}">Cancel</button>
                                    </div>
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width: 0%"></div>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                    
                    <div class="dialog-actions">
                        <div class="main-actions">
                            ${missingModels.length > 1 ? 
                                '<button class="download-all-btn p-button p-component">📥 Download All Models</button>' : ''
                            }
                            <button class="show-original-btn p-button p-component p-button-secondary">Show Original Error</button>
                        </div>
                        <div class="manual-action">
                            <button class="install-manually-btn p-button p-component p-button-outlined">📁 Install Manually</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return dialog;
    }

    showModelProgress(dialog, modelIndex, message, percentage) {
        const modelItem = dialog.querySelector(`[data-model-index="${modelIndex}"]`);
        if (!modelItem) return;
        
        const actionsDiv = modelItem.querySelector('.model-actions');
        const progressDiv = modelItem.querySelector('.model-progress');
        
        actionsDiv.style.display = 'none';
        progressDiv.style.display = 'block';
        
        const progressText = progressDiv.querySelector('.progress-text');
        const progressFill = progressDiv.querySelector('.progress-fill');
        
        if (!progressText || !progressFill) return;
        progressText.textContent = message;
        progressFill.style.width = `${percentage}%`;
    }

    showModelSuccess(dialog, modelIndex, message) {
        const modelItem = dialog.querySelector(`[data-model-index="${modelIndex}"]`);
        if (!modelItem) return;
        
        const progressDiv = modelItem.querySelector('.model-progress');
        progressDiv.innerHTML = `
            <div class="success-message">
                ✅ ${message}
            </div>
        `;
        progressDiv.style.display = 'block';
        
        // Add success styling
        modelItem.classList.add('success');
    }

    showModelError(dialog, modelIndex, errorMessage, model, onRetry, onCommunityReport) {
        const modelItem = dialog.querySelector(`[data-model-index="${modelIndex}"]`);
        if (!modelItem) return;
        
        const progressDiv = modelItem.querySelector('.model-progress');
        progressDiv.innerHTML = `
            <div class="error-message">
                ❌ ${errorMessage}
            </div>
            <div class="error-actions">
                <button class="retry-btn" data-model-index="${modelIndex}">🔄 Retry</button>
                <button class="community-btn" data-model-index="${modelIndex}">💬 Report in Community</button>
            </div>
        `;
        progressDiv.style.display = 'block';
        
        // Add error styling
        modelItem.classList.add('error');
        
        // Setup retry button
        const retryBtn = progressDiv.querySelector('.retry-btn');
        retryBtn.addEventListener('click', () => {
            modelItem.classList.remove('error');
            onRetry(model, dialog, modelIndex);
        });
        
        // Setup community button
        const communityBtn = progressDiv.querySelector('.community-btn');
        communityBtn.addEventListener('click', () => {
            onCommunityReport(model.name, errorMessage);
        });
    }

    showModelCancelled(dialog, modelIndex) {
        const modelItem = dialog.querySelector(`[data-model-index="${modelIndex}"]`);
        if (!modelItem) return;
        
        const actionsDiv = modelItem.querySelector('.model-actions');
        const progressDiv = modelItem.querySelector('.model-progress');
        
        progressDiv.style.display = 'none';
        actionsDiv.style.display = 'block';
        
        // Add cancelled styling temporarily
        modelItem.classList.add('cancelled');
        setTimeout(() => {
            modelItem.classList.remove('cancelled');
        }, 2000);
    }

    showOriginalErrorDialog(customDialog, originalErrorContent, onBackToDownload) {
        if (!originalErrorContent) {
            console.warn('No original error content available');
            return;
        }

        // Instead of creating a new dialog, replace the content of the existing dialog
        const dialogHeader = customDialog.querySelector('.p-dialog-header h3');
        const dialogContent = customDialog.querySelector('.install-missing-models-content');
        
        if (!dialogHeader || !dialogContent) {
            console.error('Could not find dialog elements to replace');
            return;
        }

        // Store the original content so we can restore it
        if (!customDialog.originalMissingModelsContent) {
            customDialog.originalMissingModelsContent = {
                headerText: dialogHeader.textContent,
                contentHTML: dialogContent.innerHTML
            };
        }

        // Update the header
        dialogHeader.textContent = '📋 Original ComfyUI Error Details';

        // Format the error content for display
        const formattedContent = this.formatOriginalErrorForDisplay(originalErrorContent);
        
        // Replace the dialog content
        dialogContent.innerHTML = `
            <div class="original-error-content">
                ${formattedContent}
            </div>
            <div class="original-error-actions">
                <button class="copy-error-btn p-button p-component p-button-secondary">📋 Copy Error Details</button>
                <button class="back-to-download-btn p-button p-component">← Back to Download</button>
            </div>
        `;
        
        // Setup event handlers for the new content
        const copyErrorBtn = dialogContent.querySelector('.copy-error-btn');
        const backToDownloadBtn = dialogContent.querySelector('.back-to-download-btn');
        
        const restoreDownloadDialog = () => {
            // Restore original header
            dialogHeader.textContent = customDialog.originalMissingModelsContent.headerText;
            
            // Restore original content
            dialogContent.innerHTML = customDialog.originalMissingModelsContent.contentHTML;
            
            // Re-setup the original event handlers
            onBackToDownload(customDialog, dialogContent);
        };
        
        backToDownloadBtn.addEventListener('click', restoreDownloadDialog);
        
        // Copy error details to clipboard
        copyErrorBtn.addEventListener('click', async () => {
            try {
                const errorText = this.formatErrorForClipboard(originalErrorContent);
                await navigator.clipboard.writeText(errorText);
                
                // Visual feedback
                const originalText = copyErrorBtn.textContent;
                copyErrorBtn.textContent = '✅ Copied!';
                copyErrorBtn.style.background = '#28a745';
                
                setTimeout(() => {
                    copyErrorBtn.textContent = originalText;
                    copyErrorBtn.style.background = '';
                }, 2000);
                
            } catch (error) {
                console.error('Failed to copy error details:', error);
                
                // Fallback - show in alert
                const errorText = this.formatErrorForClipboard(originalErrorContent);
                alert('Failed to copy to clipboard. Error details:\n\n' + errorText);
            }
        });
    }

    formatOriginalErrorForDisplay(errorContent) {
        let html = '';

        // Error timestamp
        if (errorContent.timestamp) {
            const date = new Date(errorContent.timestamp);
            html += `
                <div class="error-section">
                    <h4>⏰ Error Timestamp</h4>
                    <p class="error-timestamp">${date.toLocaleString()}</p>
                </div>
            `;
        }

        // Main error message
        if (errorContent.title) {
            html += `
                <div class="error-section">
                    <h4>🚨 Error Title</h4>
                    <p class="error-title">${this.escapeHtml(errorContent.title)}</p>
                </div>
            `;
        }

        if (errorContent.mainErrorMessage) {
            html += `
                <div class="error-section">
                    <h4>📝 Main Error Message</h4>
                    <p class="error-message">${this.escapeHtml(errorContent.mainErrorMessage)}</p>
                </div>
            `;
        }

        // Validation errors (missing models info)
        if (errorContent.validationErrors && errorContent.validationErrors.length > 0) {
            html += `
                <div class="error-section">
                    <h4>🔍 Missing Model Details</h4>
                    <div class="validation-errors">
            `;
            
            errorContent.validationErrors.forEach(valError => {
                html += `
                    <div class="validation-error-item">
                        <strong>Field:</strong> ${this.escapeHtml(valError.field)}<br>
                        <strong>Missing File:</strong> ${this.escapeHtml(valError.value)}<br>
                        <strong>Type:</strong> ${this.escapeHtml(valError.extension.toUpperCase())} model
                    </div>
                `;
            });
            
            html += `
                    </div>
                </div>
            `;
        }

        // Node information
        if (errorContent.nodeInfo) {
            html += `
                <div class="error-section">
                    <h4>🔧 Node Information</h4>
                    <pre class="error-code">${this.escapeHtml(errorContent.nodeInfo)}</pre>
                </div>
            `;
        }

        // Stack trace
        if (errorContent.stackTrace) {
            html += `
                <div class="error-section">
                    <h4>📚 Stack Trace</h4>
                    <pre class="error-code">${this.escapeHtml(errorContent.stackTrace)}</pre>
                </div>
            `;
        }

        // Detailed logs
        if (errorContent.detailedLogs) {
            html += `
                <div class="error-section">
                    <h4>📄 Detailed Logs</h4>
                    <pre class="error-code detailed-logs">${this.escapeHtml(errorContent.detailedLogs)}</pre>
                </div>
            `;
        }

        // Full error text (collapsible)
        html += `
            <div class="error-section">
                <details class="full-error-details">
                    <summary>🔍 View Full Error Text</summary>
                    <pre class="error-code full-error-text">${this.escapeHtml(errorContent.textContent)}</pre>
                </details>
            </div>
        `;

        return html;
    }

    formatErrorForClipboard(errorContent) {
        let text = '';
        
        text += '=== ComfyUI Error Report ===\n\n';
        
        if (errorContent.timestamp) {
            text += `Timestamp: ${new Date(errorContent.timestamp).toLocaleString()}\n\n`;
        }
        
        if (errorContent.title) {
            text += `Title: ${errorContent.title}\n\n`;
        }
        
        if (errorContent.mainErrorMessage) {
            text += `Main Error: ${errorContent.mainErrorMessage}\n\n`;
        }
        
        if (errorContent.validationErrors && errorContent.validationErrors.length > 0) {
            text += 'Missing Models:\n';
            errorContent.validationErrors.forEach(valError => {
                text += `  - Field: ${valError.field}\n`;
                text += `    Missing: ${valError.value}\n`;
                text += `    Type: ${valError.extension.toUpperCase()}\n\n`;
            });
        }
        
        if (errorContent.nodeInfo) {
            text += `Node Information:\n${errorContent.nodeInfo}\n\n`;
        }
        
        if (errorContent.stackTrace) {
            text += `Stack Trace:\n${errorContent.stackTrace}\n\n`;
        }
        
        if (errorContent.detailedLogs) {
            text += `Detailed Logs:\n${errorContent.detailedLogs}\n\n`;
        }
        
        text += `Full Error Text:\n${errorContent.textContent}\n`;
        
        return text;
    }

    escapeHtml(text) {
        if (!text) return '';
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    removeBackdropElements() {
        // Remove various types of backdrop elements that might be present
        const backdropSelectors = [
            '.p-dialog-mask',
            '.p-component-overlay',
            '.modal-backdrop',
            '.dialog-backdrop',
            '.overlay',
            '[data-pc-section="mask"]',
            '.p-dialog-mask-enter-done',
            '.p-dialog-mask-leave-done'
        ];
        
        backdropSelectors.forEach(selector => {
            const backdrops = document.querySelectorAll(selector);
            backdrops.forEach(backdrop => {
                // Check if this backdrop is associated with our dialog or is orphaned
                const isOrphaned = !backdrop.querySelector('.install-missing-models-dialog');
                
                // Remove PrimeVue dialog masks and other modal backdrops
                if (isOrphaned || selector.includes('p-dialog-mask') || selector.includes('backdrop')) {
                    console.log(`🗑️ Removing backdrop element: ${selector}`);
                    backdrop.remove();
                }
            });
        });
        
        // Also check for any dialog containers that might be empty now
        const dialogContainers = document.querySelectorAll('.p-dialog-root, .modal-root, .dialog-root');
        dialogContainers.forEach(container => {
            // If container has no visible dialogs, remove it
            const visibleDialogs = container.querySelectorAll('.p-dialog:not([style*="display: none"])');
            if (visibleDialogs.length === 0) {
                console.log(`🗑️ Removing empty dialog container`);
                container.remove();
            }
        });
        
        // Reset body styles that might have been applied by modal systems
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
        document.body.classList.remove('p_overflow-hidden', 'modal-open');
        
        // Remove any injected CSS that might be related to modal display
        const injectedStyles = document.querySelectorAll('style[data-pc-name], style[data-modal]');
        injectedStyles.forEach(style => {
            if (style.textContent.includes('p-dialog-mask') || style.textContent.includes('modal-backdrop')) {
                style.remove();
            }
        });
    }

    addCustomStyles() {
        if (document.getElementById('missing-installed-models-custom-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'missing-installed-models-custom-styles';
        style.textContent = `
            /* Remove blue background from header and match app styles */
            .global-dialog .p-dialog-header {
                background: var(--comfy-menu-bg, #353535);
                color: var(--input-text, #fff);
                padding: 16px;
                border-bottom: 1px solid var(--border-color, #666);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .manual-installation-span {
                color: #007bff;
                cursor: pointer;
                text-decoration: underline;
                font-weight: 500;
            }
            
            .global-dialog .p-dialog-header h3 {
                margin: 0;
                font-size: 18px;
                font-weight: 500;
                color: var(--input-text, #fff);
            }
            
            .global-dialog .close-btn {
                color: var(--input-text, #fff);
                background: none;
                border: none;
                cursor: pointer;
                padding: 8px;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background-color 0.2s;
            }
            
            .global-dialog .close-btn:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .global-dialog .p-dialog-content {
                padding: 0;
                background: var(--comfy-menu-bg, #353535);
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            
            .global-dialog .install-missing-models-content {
                padding: 20px;
            }
            
            .global-dialog .error-explanation {
                display: flex;
                align-items: center;
                background: rgba(255, 255, 255, 0.05);
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 16px;
            }
            
            .global-dialog .error-icon {
                margin-right: 12px;
            }
            
            .global-dialog .error-text {
                flex: 1;
            }
            
            .global-dialog .missing-models-list {
                max-height: 400px;
                overflow-y: auto;
                margin-bottom: 16px;
            }
            
            .global-dialog .missing-model-item {
                padding: 16px;
                border: 1px solid var(--border-color, #666);
                border-radius: 6px;
                margin-bottom: 12px;
                background: rgba(255, 255, 255, 0.02);
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
            }
            
            .global-dialog .missing-model-item.success {
                border-color: #28a745;
                background: rgba(40, 167, 69, 0.1);
            }
            
            .global-dialog .missing-model-item.error {
                border-color: #dc3545;
                background: rgba(220, 53, 69, 0.1);
            }
            
            .global-dialog .missing-model-item.cancelled {
                border-color: #ffc107;
                background: rgba(255, 193, 7, 0.1);
            }
            
            .global-dialog .model-info {
                flex: 1;
                min-width: 0;
            }
            
            .global-dialog .model-name {
                font-weight: 600;
                color: var(--input-text, #fff);
                margin-bottom: 4px;
                word-break: break-word;
            }
            
            .global-dialog .model-details {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
            }
            
            .global-dialog .model-category,
            .global-dialog .model-field,
            .global-dialog .model-context {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.7);
                background: rgba(255, 255, 255, 0.1);
                padding: 2px 6px;
                border-radius: 3px;
            }
            
            .global-dialog .model-actions {
                flex-shrink: 0;
            }
            
            .global-dialog .download-btn, 
            .global-dialog .retry-btn, 
            .global-dialog .community-btn, 
            .global-dialog .cancel-btn {
                background: #007bff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                transition: background 0.2s ease;
            }
            
            .global-dialog .download-btn:hover, 
            .global-dialog .retry-btn:hover {
                background: #0056b3;
            }
            
            .global-dialog .community-btn {
                background: #6f42c1;
                margin-left: 8px;
            }
            
            .global-dialog .community-btn:hover {
                background: #5a2d91;
            }
            
            .global-dialog .cancel-btn {
                background: #dc3545;
            }
            
            .global-dialog .cancel-btn:hover {
                background: #c82333;
            }
            
            .global-dialog .model-progress {
                flex: 1;
                margin-left: 12px;
            }
            
            .global-dialog .progress-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .global-dialog .progress-text {
                font-size: 12px;
                color: var(--input-text, #fff);
            }
            
            .global-dialog .progress-bar {
                width: 100%;
                height: 6px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 3px;
                overflow: hidden;
            }
            
            .global-dialog .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #007bff, #0056b3);
                transition: width 0.3s ease;
                border-radius: 3px;
            }
            
            .global-dialog .success-message {
                color: #28a745;
                font-size: 12px;
                font-weight: 600;
            }
            
            .global-dialog .error-message {
                color: #dc3545;
                font-size: 12px;
                margin-bottom: 8px;
            }
            
            .global-dialog .error-actions {
                display: flex;
                gap: 8px;
            }
            
            .global-dialog .dialog-actions {
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                gap: 12px;
                border-top: 1px solid var(--border-color, #666);
                padding-top: 20px;
            }
            
            .global-dialog .main-actions {
                display: flex;
                gap: 12px;
                flex: 1;
            }
            
            .global-dialog .manual-action {
                flex-shrink: 0;
            }
            
            .global-dialog .download-all-btn, 
            .global-dialog .show-original-btn,
            .global-dialog .install-manually-btn {
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.2s ease;
                font-size: 14px;
            }
            
            .global-dialog .download-all-btn {
                background: #28a745;
                color: white;
                flex: 1;
            }
            
            .global-dialog .download-all-btn:hover {
                background: #218838;
            }
            
            .global-dialog .download-all-btn:disabled {
                background: #6c757d;
                cursor: not-allowed;
            }
            
            .global-dialog .show-original-btn {
                background: #6c757d;
                color: white;
                flex: 0 0 auto;
            }
            
            .global-dialog .show-original-btn:hover {
                background: #5a6268;
            }
            
            .global-dialog .install-manually-btn {
                background: transparent;
                color: var(--input-text, #fff);
                border: 2px solid var(--border-color, #666);
                position: relative;
            }
            
            .global-dialog .install-manually-btn:hover {
                background: rgba(255, 255, 255, 0.1);
                border-color: var(--input-text, #fff);
                transform: translateY(-1px);
            }
            
            .global-dialog .install-manually-btn:active {
                transform: translateY(0);
            }

            /* Original error dialog styles */
            .original-error-dialog .p-dialog-content {
                max-height: 70vh;
                overflow-y: auto;
            }
            
            .original-error-content {
                padding: 20px;
                color: var(--input-text, #fff);
            }
            
            .error-section {
                margin-bottom: 20px;
                padding: 15px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 6px;
                border-left: 4px solid #007bff;
            }
            
            .error-section h4 {
                margin: 0 0 10px 0;
                color: #007bff;
                font-size: 14px;
                font-weight: 600;
            }
            
            .error-section p {
                margin: 0;
                line-height: 1.5;
            }
            
            .error-title, .error-message {
                background: rgba(220, 53, 69, 0.1);
                padding: 10px;
                border-radius: 4px;
                border-left: 3px solid #dc3545;
                font-weight: 500;
            }
            
            .error-timestamp {
                font-family: monospace;
                background: rgba(255, 255, 255, 0.1);
                padding: 5px 10px;
                border-radius: 4px;
                display: inline-block;
            }
            
            .validation-errors {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            
            .validation-error-item {
                background: rgba(255, 193, 7, 0.1);
                padding: 10px;
                border-radius: 4px;
                border-left: 3px solid #ffc107;
                font-size: 13px;
            }
            
            .error-code {
                background: rgba(0, 0, 0, 0.3);
                padding: 15px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
                margin: 10px 0;
                overflow-x: auto;
                white-space: pre-wrap;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .detailed-logs {
                max-height: 200px;
                overflow-y: auto;
            }
            
            .full-error-details {
                margin-top: 10px;
            }
            
            .full-error-details summary {
                cursor: pointer;
                padding: 10px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                outline: none;
            }
            
            .full-error-details summary:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .full-error-text {
                max-height: 300px;
                overflow-y: auto;
                margin-top: 10px;
            }
            
            .original-error-actions {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                padding: 20px;
                border-top: 1px solid var(--border-color, #666);
                background: rgba(255, 255, 255, 0.02);
            }
            
            .copy-error-btn {
                background: #6c757d;
                color: white;
                transition: background 0.2s ease;
            }
            
            .copy-error-btn:hover {
                background: #5a6268;
            }
        `;
        
        document.head.appendChild(style);
    }
}