import { api } from "../../scripts/api.js";
import { MissingModelUI } from "./MissingModelUI.js";

export class MissingModelsManager {
    constructor() {
        this.activeDownloads = new Map();
        this.observer = null;
        this.isInitialized = false;
        this.ui = new MissingModelUI();
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        this.isInitialized = true;
        
        console.log("🔧 Initializing Missing Models Manager");
        this.setupMutationObserver();
        
        // Check for existing dialogs on initialization
        setTimeout(() => this.checkExistingDialogs(), 1000);
    }

    setupMutationObserver() {
        this.observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        this.checkForPromptFailureDialog(node);
                    }
                });
            });
        });
        
        this.observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    checkExistingDialogs() {
        const existingDialogs = document.querySelectorAll('.p-dialog.global-dialog');
        existingDialogs.forEach(dialog => {
            this.checkForPromptFailureDialog(dialog);
        });
    }

    checkForPromptFailureDialog(element) {
        const dialog = element.classList?.contains('global-dialog') ? element : 
                      element.querySelector?.('.p-dialog.global-dialog');
        
        if (!dialog) return;
        
        const dialogContent = dialog.textContent || '';
        const hasPromptFailure = dialogContent.includes('Prompt execution failed') ||
                                dialogContent.includes('Prompt outputs failed validation');
        
        const hasModelError = dialogContent.includes('Value not in list') ||
                             dialogContent.includes('not in [') ||
                             this.hasModelFieldError(dialogContent);
        
        if (hasPromptFailure && hasModelError) {
            console.log("🎯 Found prompt failure dialog with missing model, replacing with custom version");
            this.replacePromptFailureDialog(dialog);
        }
    }

    hasModelFieldError(dialogContent) {
        const modelFieldPatterns = [
            /\w+_name:\s*['"][^'"]*\.(safetensors|ckpt|pt|pth|bin)['"][^'"]*/gi,
            /\w+:\s*['"][^'"]*\.(safetensors|ckpt|pt|pth|bin)['"][^'"]*/gi,
            /model:\s*['"][^'"]*\.(safetensors|ckpt|pt|pth|bin)['"][^'"]*/gi,
            /checkpoint:\s*['"][^'"]*\.(safetensors|ckpt|pt|pth|bin)['"][^'"]*/gi
        ];
        
        return modelFieldPatterns.some(pattern => pattern.test(dialogContent));
    }

    replacePromptFailureDialog(originalDialog) {
        const missingModels = this.extractMissingModelFromError(originalDialog);
        
        if (missingModels.length === 0) {
            console.warn("No missing models found in dialog");
            return;
        }
        
        const originalErrorContent = this.captureOriginalErrorContent(originalDialog);
        
        const dialogContainer = originalDialog.parentNode;
        originalDialog.remove();
        
        this.showCustomMissingModelsDialog(missingModels, dialogContainer, originalErrorContent);
    }

    captureOriginalErrorContent(originalDialog) {
        const errorContent = {
            timestamp: new Date().toISOString(),
            fullHTML: originalDialog.outerHTML,
            textContent: originalDialog.textContent || '',
            title: '',
            mainErrorMessage: '',
            detailedLogs: '',
            stackTrace: '',
            nodeInfo: '',
            validationErrors: []
        };

        try {
            // Extract dialog title
            const titleElement = originalDialog.querySelector('.p-dialog-header h2, .p-dialog-header h3, .p-dialog-header .p-dialog-title, h1, h2, h3');
            if (titleElement) {
                errorContent.title = titleElement.textContent.trim();
            }

            // Extract main error message
            const contentArea = originalDialog.querySelector('.p-dialog-content, .dialog-content, .modal-content');
            if (contentArea) {
                const errorPatterns = [
                    'Prompt execution failed',
                    'Prompt outputs failed validation',
                    'Error:',
                    'Exception:',
                    'Failed to',
                    'Unable to'
                ];

                const contentText = contentArea.textContent;
                for (const pattern of errorPatterns) {
                    const index = contentText.indexOf(pattern);
                    if (index !== -1) {
                        const afterPattern = contentText.substring(index);
                        
                        const endIndex = Math.min(
                            afterPattern.indexOf('\n') !== -1 ? afterPattern.indexOf('\n') : 200,
                            afterPattern.indexOf('.') !== -1 ? afterPattern.indexOf('.') + 1 : 200,
                            200
                        );
                        
                        errorContent.mainErrorMessage = afterPattern.substring(0, endIndex).trim();
                        break;
                    }
                }

                if (!errorContent.mainErrorMessage) {
                    const firstParagraph = contentArea.querySelector('p, div');
                    if (firstParagraph) {
                        errorContent.mainErrorMessage = firstParagraph.textContent.trim().substring(0, 200);
                    }
                }
            }

            // Extract detailed logs
            const logElements = originalDialog.querySelectorAll('pre, code, .log, .error-details, [style*="monospace"], [class*="code"], [class*="log"]');
            if (logElements.length > 0) {
                errorContent.detailedLogs = Array.from(logElements)
                    .map(el => el.textContent.trim())
                    .filter(text => text.length > 10)
                    .join('\n\n--- Log Section ---\n\n');
            }

            // Extract stack trace information
            const stackTracePatterns = [
                /File ".*", line \d+/g,
                /Traceback \(most recent call last\):/g,
                /at \w+\.[a-zA-Z_$][\w$]*\s*\(/g,
                /^\s*at\s+/gm
            ];

            for (const pattern of stackTracePatterns) {
                const matches = errorContent.textContent.match(pattern);
                if (matches && matches.length > 0) {
                    errorContent.stackTrace += matches.join('\n') + '\n';
                }
            }

            // Extract node information
            const nodeInfoPatterns = [
                /Node:\s*(\w+)/gi,
                /(\w+Loader|\w+Model|\w+Node):/gi,
                /class_type:\s*['"]([^'"]+)['"]/gi
            ];

            for (const pattern of nodeInfoPatterns) {
                const matches = errorContent.textContent.matchAll(pattern);
                for (const match of matches) {
                    errorContent.nodeInfo += `${match[0]}\n`;
                }
            }

            // Extract validation errors
            const validationPattern = /(\w+):\s*['"]([^'"]*\.(safetensors|ckpt|pt|pth|bin))['"][^'"]*not\s+in\s*\[([^\]]*)\]/gi;
            let validationMatch;
            
            while ((validationMatch = validationPattern.exec(errorContent.textContent)) !== null) {
                errorContent.validationErrors.push({
                    field: validationMatch[1],
                    value: validationMatch[2],
                    extension: validationMatch[3],
                    availableValues: validationMatch[4]
                });
            }

            // Clean up the text content
            errorContent.textContent = errorContent.textContent
                .replace(/\s+/g, ' ')
                .replace(/\n\s*\n/g, '\n')
                .trim();

        } catch (error) {
            console.error('Error capturing original error content:', error);
            errorContent.captureError = error.message;
        }

        return errorContent;
    }

    showCustomMissingModelsDialog(missingModels, dialogContainer, originalErrorContent) {
        const customDialog = this.ui.createCustomDialog(missingModels);
        
        customDialog.originalErrorContent = originalErrorContent;
        
        dialogContainer.appendChild(customDialog);
        
        this.setupCustomDialogHandlers(customDialog, missingModels, null);
    }

    extractMissingModelFromError(dialog) {
        const models = [];
        
        try {
            const dialogContent = dialog.textContent || '';
            
            // Enhanced pattern to capture node class information
            const fieldValuePattern = /(\w+):\s*['"]([^'"]*\.(safetensors|ckpt|pt|pth|bin))['"][^'"]*not\s+in\s*\[/gi;
            
            // Pattern to extract node class type from error messages
            const nodeClassPattern = /(?:node\s+)?(\w+(?:Loader|Model|Checkpoint))\s*\(.*?\)/gi;
            const nodeValidationPattern = /(\w+(?:Loader|Model|Checkpoint)).*?validation/gi;
            
            // Extract node class types from the error
            const nodeClasses = new Set();
            let nodeMatch;
            
            // Try different patterns to find node class
            while ((nodeMatch = nodeClassPattern.exec(dialogContent)) !== null) {
                nodeClasses.add(nodeMatch[1]);
            }
            
            // Reset regex
            nodeValidationPattern.lastIndex = 0;
            while ((nodeMatch = nodeValidationPattern.exec(dialogContent)) !== null) {
                nodeClasses.add(nodeMatch[1]);
            }
            
            console.log(`🔍 Detected node classes from error: ${Array.from(nodeClasses).join(', ')}`);
            
            let match;
            while ((match = fieldValuePattern.exec(dialogContent)) !== null) {
                const fieldName = match[1];
                const fullModelName = match[2];
                const extension = match[3];
                
                const baseName = fullModelName.replace(/\.(safetensors|ckpt|pt|pth|bin)$/i, '');
                
                // Try to find the specific node class for this field
                let specificNodeType = null;
                for (const nodeClass of nodeClasses) {
                    if (this.isFieldCompatibleWithNode(fieldName, nodeClass)) {
                        specificNodeType = nodeClass;
                        break;
                    }
                }
                
                const { nodeType, category } = this.inferTypeFromFieldName(fieldName);
                const finalNodeType = specificNodeType || nodeType;
                
                models.push({
                    name: fullModelName,
                    baseName: baseName,
                    category: category,
                    nodeType: finalNodeType,  // Use the detected node class if available
                    fullPath: `${category}/${fullModelName}`,
                    fieldName: fieldName,
                    errorContext: `${fieldName} field validation error`
                });
                
                console.log(`📝 Extracted model info: ${fullModelName} from field: ${fieldName} -> ${finalNodeType}/${category}`);
            }
            
            // Fallback pattern
            if (models.length === 0) {
                const filePattern = /['"]([^'"]*\.(safetensors|ckpt|pt|pth|bin))['"][^'"]*not\s+in\s*\[/gi;
                let fileMatch;
                
                while ((fileMatch = filePattern.exec(dialogContent)) !== null) {
                    const fullModelName = fileMatch[1];
                    const baseName = fullModelName.replace(/\.(safetensors|ckpt|pt|pth|bin)$/i, '');
                    
                    const { nodeType, category } = this.inferTypeFromFileName(fullModelName);
                    
                    // Use the first detected node class if available
                    const finalNodeType = nodeClasses.size > 0 ? Array.from(nodeClasses)[0] : nodeType;
                    
                    models.push({
                        name: fullModelName,
                        baseName: baseName,
                        category: category,
                        nodeType: finalNodeType,
                        fullPath: `${category}/${fullModelName}`,
                        fieldName: 'unknown_field',
                        errorContext: 'File validation error'
                    });
                    
                    console.log(`📝 Fallback extracted: ${fullModelName} -> ${finalNodeType}/${category}`);
                }
            }
            
        } catch (error) {
            console.error('Error parsing prompt failure dialog:', error);
        }
        
        return models;
    }

    isFieldCompatibleWithNode(fieldName, nodeClass) {
        /**
         * Determine if a field name is compatible with a specific node class
         */
        const fieldLower = fieldName.toLowerCase();
        const nodeLower = nodeClass.toLowerCase();
        
        const compatibilityMap = {
            'ckpt_name': ['checkpointloader', 'checkpointloadersimple'],
            'checkpoint_name': ['checkpointloader', 'checkpointloadersimple'],
            'model_name': ['checkpointloader', 'checkpointloadersimple'],
            'vae_name': ['vaeloader'],
            'lora_name': ['loraloader', 'loraloadermodelonly'],
            'controlnet_name': ['controlnetloader', 'diffcontrolnetloader'],
            'upscale_model': ['upscalemodelloader'],
            'clip_name': ['cliploader', 'dualcliploader'],
            'unet_name': ['unetloader'],
            'style_model': ['stylemodelloader'],
            'gligen': ['gligenloader']
        };
        
        const compatibleNodes = compatibilityMap[fieldLower] || [];
        return compatibleNodes.some(node => nodeLower.includes(node));
    }

    inferTypeFromFieldName(fieldName) {
        const fieldLower = fieldName.toLowerCase();
        
        const fieldMappings = {
            'ckpt_name': { nodeType: 'checkpoint', category: 'checkpoints' },
            'checkpoint_name': { nodeType: 'checkpoint', category: 'checkpoints' },
            'model_name': { nodeType: 'checkpoint', category: 'checkpoints' },
            'lora_name': { nodeType: 'lora', category: 'loras' },
            'lyco_name': { nodeType: 'lora', category: 'loras' },
            'vae_name': { nodeType: 'vae', category: 'vae' },
            'controlnet_name': { nodeType: 'controlnet', category: 'controlnet' },
            'control_net_name': { nodeType: 'controlnet', category: 'controlnet' },
            'upscale_model': { nodeType: 'upscale', category: 'upscale_models' },
            'upscaler_name': { nodeType: 'upscale', category: 'upscale_models' },
            'clip_name': { nodeType: 'clip', category: 'clip' },
            'embedding_name': { nodeType: 'embedding', category: 'embeddings' },
            'textual_inversion': { nodeType: 'embedding', category: 'embeddings' }
        };
        
        if (fieldMappings[fieldLower]) {
            return fieldMappings[fieldLower];
        }
        
        // Try partial matches
        if (fieldLower.includes('lora')) return { nodeType: 'lora', category: 'loras' };
        if (fieldLower.includes('vae')) return { nodeType: 'vae', category: 'vae' };
        if (fieldLower.includes('controlnet') || fieldLower.includes('control_net')) {
            return { nodeType: 'controlnet', category: 'controlnet' };
        }
        if (fieldLower.includes('upscale')) return { nodeType: 'upscale', category: 'upscale_models' };
        if (fieldLower.includes('clip')) return { nodeType: 'clip', category: 'clip' };
        if (fieldLower.includes('embedding')) return { nodeType: 'embedding', category: 'embeddings' };
        if (fieldLower.includes('checkpoint') || fieldLower.includes('ckpt')) {
            return { nodeType: 'checkpoint', category: 'checkpoints' };
        }
        
        return { nodeType: 'checkpoint', category: 'checkpoints' };
    }

    inferTypeFromFileName(fileName) {
        const nameLower = fileName.toLowerCase();
        
        if (nameLower.includes('lora') || nameLower.includes('lyco')) {
            return { nodeType: 'lora', category: 'loras' };
        }
        if (nameLower.includes('vae')) {
            return { nodeType: 'vae', category: 'vae' };
        }
        if (nameLower.includes('controlnet') || nameLower.includes('control_net')) {
            return { nodeType: 'controlnet', category: 'controlnet' };
        }
        if (nameLower.includes('upscal') || nameLower.includes('esrgan')) {
            return { nodeType: 'upscale', category: 'upscale_models' };
        }
        if (nameLower.includes('clip')) {
            return { nodeType: 'clip', category: 'clip' };
        }
        if (nameLower.includes('embedding') || nameLower.includes('textual')) {
            return { nodeType: 'embedding', category: 'embeddings' };
        }
        
        return { nodeType: 'checkpoint', category: 'checkpoints' };
    }

    inferTypeFromNodeClass(nodeClassName) {
        const classLower = nodeClassName.toLowerCase();
        
        if (classLower.includes('lora')) return { nodeType: 'lora', category: 'loras' };
        if (classLower.includes('vae')) return { nodeType: 'vae', category: 'vae' };
        if (classLower.includes('controlnet')) return { nodeType: 'controlnet', category: 'controlnet' };
        if (classLower.includes('upscale')) return { nodeType: 'upscale', category: 'upscale_models' };
        if (classLower.includes('clip')) return { nodeType: 'clip', category: 'clip' };
        if (classLower.includes('embedding')) return { nodeType: 'embedding', category: 'embeddings' };
        if (classLower.includes('checkpoint')) return { nodeType: 'checkpoint', category: 'checkpoints' };
        
        return { nodeType: 'checkpoint', category: 'checkpoints' };
    }

    setupCustomDialogHandlers(dialog, missingModels, originalDialog) {
        dialog.missingModelsData = missingModels;
        
        const closeBtn = dialog.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            this.closeCustomDialog(dialog, null);
        });
        
        const dialogContent = dialog.querySelector('.install-missing-models-content');
        this.setupDownloadContentHandlers(dialog, dialogContent);
        
        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) {
                this.closeCustomDialog(dialog, null);
            }
        });
    }

    setupDownloadContentHandlers(dialog, dialogContent) {
        const missingModelsData = dialog.missingModelsData;
        if (!missingModelsData) {
            console.warn('Missing models data not found for re-setup');
            return;
        }
        
        // Individual download buttons
        const downloadButtons = dialogContent.querySelectorAll('.download-btn');
        downloadButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modelIndex = parseInt(e.target.dataset.modelIndex);
                this.downloadSingleModel(missingModelsData[modelIndex], dialog, modelIndex);
            });
        });
        
        // Download all button
        const downloadAllBtn = dialogContent.querySelector('.download-all-btn');
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener('click', () => {
                this.downloadAllModels(missingModelsData, dialog);
            });
        }
        
        // Show original error button
        const showOriginalBtn = dialogContent.querySelector('.show-original-btn');
        if (showOriginalBtn) {
            showOriginalBtn.addEventListener('click', () => {
                this.ui.showOriginalErrorDialog(
                    dialog, 
                    dialog.originalErrorContent, 
                    (customDialog, dialogContent) => this.setupDownloadContentHandlers(customDialog, dialogContent)
                );
            });
        }
        
        // Install Manually button
        const installManuallyBtn = dialogContent.querySelector('.install-manually-btn');
        const manualInstallLink = dialogContent.querySelector('.manual-installation-span');
        if (installManuallyBtn) {
            installManuallyBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.openFileSystemManager(dialog);
            });
        }

        if (manualInstallLink) {
            manualInstallLink.addEventListener('click', (e) => {
                e.preventDefault();
                this.openFileSystemManager(dialog);
            });
        }
        
        // Cancel buttons
        const cancelButtons = dialogContent.querySelectorAll('.cancel-btn');
        cancelButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modelIndex = parseInt(e.target.dataset.modelIndex);
                this.cancelModelDownload(missingModelsData[modelIndex], dialog, modelIndex);
            });
        });
    }

    openFileSystemManager(dialog) {
        this.closeCustomDialog(dialog, null);
        
        if (window.fileSystemManager) {
            console.log("📁 Opening File System Manager for manual installation");
            window.fileSystemManager.showModal();
        } else {
            console.error("File System Manager not available");
            alert("File System Manager is not available. Please refresh the page and try again.");
        }
    }

    async downloadSingleModel(model, dialog, modelIndex) {
        const sessionId = `missing_model_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        try {
            this.ui.showModelProgress(dialog, modelIndex, "Starting download...", 0);
            
            const response = await api.fetchApi('/filesystem/download_missing_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_name: model.name,
                    node_type: model.nodeType,
                    field_name: model.fieldName,  // Include field name for VAE disambiguation
                    session_id: sessionId
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.activeDownloads.set(`${modelIndex}`, sessionId);
                this.pollModelProgress(sessionId, dialog, modelIndex, model);
            } else {
                this.ui.showModelError(dialog, modelIndex, result.error, model, 
                    (model, dialog, modelIndex) => this.downloadSingleModel(model, dialog, modelIndex),
                    (modelName, errorMessage) => this.reportToCommunity(modelName, errorMessage)
                );
            }
            
        } catch (error) {
            this.ui.showModelError(dialog, modelIndex, error.message, model,
                (model, dialog, modelIndex) => this.downloadSingleModel(model, dialog, modelIndex),
                (modelName, errorMessage) => this.reportToCommunity(modelName, errorMessage)
            );
        }
    }

    async downloadAllModels(missingModels, dialog) {
        const downloadAllBtn = dialog.querySelector('.download-all-btn');
        downloadAllBtn.disabled = true;
        downloadAllBtn.textContent = 'Downloading...';
        
        for (let i = 0; i < missingModels.length; i++) {
            if (i > 0) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
            await this.downloadSingleModel(missingModels[i], dialog, i);
        }
    }

    pollModelProgress(sessionId, dialog, modelIndex, model) {
        const pollInterval = setInterval(async () => {
            try {
                const response = await api.fetchApi(`/filesystem/missing_model_progress/${sessionId}`);
                const progress = await response.json();
                
                this.ui.showModelProgress(dialog, modelIndex, progress.message, progress.percentage);
                
                if (['completed', 'error', 'cancelled'].includes(progress.status)) {
                    clearInterval(pollInterval);
                    this.activeDownloads.delete(`${modelIndex}`);
                    
                    if (progress.status === 'completed') {
                        this.ui.showModelSuccess(dialog, modelIndex, progress.message);
                    } else if (progress.status === 'error') {
                        this.ui.showModelError(dialog, modelIndex, progress.message, model,
                            (model, dialog, modelIndex) => this.downloadSingleModel(model, dialog, modelIndex),
                            (modelName, errorMessage) => this.reportToCommunity(modelName, errorMessage)
                        );
                    } else if (progress.status === 'cancelled') {
                        this.ui.showModelCancelled(dialog, modelIndex);
                    }
                }
                
            } catch (error) {
                console.error('Error polling progress:', error);
                clearInterval(pollInterval);
                this.activeDownloads.delete(`${modelIndex}`);
                this.ui.showModelError(dialog, modelIndex, 'Failed to check download progress', model,
                    (model, dialog, modelIndex) => this.downloadSingleModel(model, dialog, modelIndex),
                    (modelName, errorMessage) => this.reportToCommunity(modelName, errorMessage)
                );
            }
        }, 1000);
    }

    async cancelModelDownload(model, dialog, modelIndex) {
        const sessionId = this.activeDownloads.get(`${modelIndex}`);
        if (!sessionId) return;
        
        try {
            await api.fetchApi('/filesystem/cancel_missing_model_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            });
            
        } catch (error) {
            console.error('Error cancelling download:', error);
        }
    }

    async reportToCommunity(modelName, errorMessage) {
        try {
            const response = await api.fetchApi('/filesystem/get_community_link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_name: modelName,
                    error_logs: errorMessage,
                    runpod_id: this.getRunPodId()
                })
            });
            
            const result = await response.json();
            
            if (result.success && result.community_link) {
                window.open(result.community_link, '_blank');
            } else {
                console.error('Failed to get community link');
                window.open('https://discord.gg/your-server', '_blank');
            }
            
        } catch (error) {
            console.error('Error reporting to community:', error);
            window.open('https://discord.gg/your-server', '_blank');
        }
    }

    getRunPodId() {
        return process.env.RUNPOD_POD_ID || 
               window.RUNPOD_POD_ID || 
               localStorage.getItem('runpod_id') || 
               'unknown';
    }

    closeCustomDialog(dialog, originalDialog) {
        // Cancel any active downloads
        this.activeDownloads.forEach((sessionId) => {
            api.fetchApi('/filesystem/cancel_missing_model_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            }).catch(console.error);
        });
        
        this.activeDownloads.clear();
        
        // Don't remove backdrop elements - ComfyUI needs them for future dialogs
        // this.ui.removeBackdropElements();
        
        // Remove custom dialog
        dialog.remove();
        
        console.log("Missing models dialog closed");
    }

    destroy() {
        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }
        
        this.activeDownloads.forEach((sessionId) => {
            api.fetchApi('/filesystem/cancel_missing_model_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            }).catch(console.error);
        });
        
        this.activeDownloads.clear();
        this.isInitialized = false;
    }
}
