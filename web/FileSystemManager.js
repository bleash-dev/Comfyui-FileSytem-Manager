import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { UIComponents } from "./UIComponents.js";
import { Dialog } from "./Dialog.js";

export class FileSystemManager {
    constructor() {
        this.modal = null;
        this.uploadModal = null;
        this.currentPath = '';
        this.selectedItems = new Set();
        this.currentContents = [];
        this.isCreatingFolder = false;
        this.uploadProgressInterval = null;
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
    }

    createModal() {
        const modal = UIComponents.createModal();
        this.setupEventListeners(modal);
        return modal;
    }

    setupEventListeners(modal) {
        // Close modal
        modal.querySelector('#fs-close').addEventListener('click', () => this.closeModal());
        
        // Actions
        modal.querySelector('#fs-create-folder').addEventListener('click', () => this.showCreateFolderForm());
        modal.querySelector('#fs-upload').addEventListener('click', () => this.showUploadModal());
        modal.querySelector('#fs-download-selected').addEventListener('click', () => this.downloadSelected());
        modal.querySelector('#fs-delete').addEventListener('click', () => this.deleteSelected());
        modal.querySelector('#fs-refresh').addEventListener('click', () => this.refreshCurrentDirectory());
        
        // Create folder form
        modal.querySelector('#fs-create-confirm').addEventListener('click', () => this.createFolder());
        modal.querySelector('#fs-create-cancel').addEventListener('click', () => this.hideCreateFolderForm());
        modal.querySelector('#fs-folder-name').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.createFolder();
            if (e.key === 'Escape') this.hideCreateFolderForm();
        });
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    showUploadModal() {
        if (this.uploadModal) {
            this.closeUploadModal();
        }
        
        this.uploadModal = UIComponents.createUploadModal();
        this.setupUploadEventListeners(this.uploadModal);
        document.body.appendChild(this.uploadModal);
        
        UIComponents.showUploadOptions(this.uploadModal);
    }

    closeUploadModal() {
        if (this.uploadModal) {
            document.body.removeChild(this.uploadModal);
            this.uploadModal = null;
        }
        this.stopUploadProgressPolling();
    }

    setupUploadEventListeners(modal) {
        // Close upload modal
        modal.querySelector('#fs-upload-close').addEventListener('click', () => this.closeUploadModal());
        
        // Upload option selection
        modal.querySelectorAll('.fs-upload-option').forEach(option => {
            option.addEventListener('click', () => {
                const type = option.dataset.type;
                UIComponents.showUploadForm(modal, type);
            });
        });
        
        // Back button
        modal.querySelector('#fs-upload-back').addEventListener('click', () => {
            UIComponents.showUploadOptions(modal);
        });
        
        // Upload actions
        modal.querySelector('#fs-upload-start').addEventListener('click', () => this.startUpload());
        modal.querySelector('#fs-upload-cancel').addEventListener('click', () => this.closeUploadModal());
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeUploadModal();
            }
        });
    }

    async showModal() {
        if (this.modal) {
            this.closeModal();
        }
        
        this.modal = this.createModal();
        document.body.appendChild(this.modal);
        
        // Load root directory
        await this.navigateToPath('');
    }

    closeModal() {
        if (this.modal) {
            document.body.removeChild(this.modal);
            this.modal = null;
        }
        // Ensure upload modal and its polling are also closed
        if (this.uploadModal) {
            this.closeUploadModal();
        }
        this.currentPath = '';
        this.selectedItems = new Set();
        this.currentContents = [];
        this.isCreatingFolder = false;
        this.uploadProgressInterval = null;
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
    }

    updateBreadcrumb() {
        if (!this.modal) return;
        UIComponents.updateBreadcrumb(this.modal, this.currentPath, (path) => this.navigateToPath(path));
    }

    async navigateToPath(path) {
        try {
            console.log('Navigating to path:', path);
            UIComponents.showStatus(this.modal, 'Loading...');
            
            const response = await api.fetchApi(`/filesystem/browse?path=${encodeURIComponent(path)}`);
            const result = await response.json();
            
            console.log('Navigation result:', result);
            
            if (result.success) {
                this.currentPath = path;
                this.currentContents = result.contents;
                this.selectedItems.clear();
                this.updateBreadcrumb();
                this.renderContents();
                this.updateActions();
                UIComponents.showStatus(this.modal, 'Ready');
            } else {
                UIComponents.showMessage(this.modal, result.error, true);
                UIComponents.showStatus(this.modal, 'Error');
            }
        } catch (error) {
            console.error('Navigation error:', error);
            UIComponents.showMessage(this.modal, `Error loading directory: ${error.message}`, true);
            UIComponents.showStatus(this.modal, 'Error');
        }
    }

    renderContents() {
        if (!this.modal) return;
        
        UIComponents.renderContents(
            this.modal,
            this.currentContents,
            (item, e) => this.handleItemClick(item, e),
            (item) => this.handleItemDoubleClick(item)
        );
        
        this.updateItemCount();
    }

    handleItemClick(item, e) {
        const itemPath = item.path;
        if (e.ctrlKey || e.metaKey) {
            this.toggleSelection(itemPath);
        } else {
            this.clearSelection();
            if (item.type === 'directory') {
                console.log('Directory clicked, navigating to:', itemPath);
                this.navigateToPath(itemPath);
            } else {
                this.selectItem(itemPath);
            }
        }
    }

    handleItemDoubleClick(item) {
        if (item.type === 'directory') {
            console.log('Directory double-clicked, navigating to:', item.path);
            this.navigateToPath(item.path);
        }
    }

    selectItem(path) {
        this.selectedItems.clear();
        this.selectedItems.add(path);
        this.updateSelection();
        this.updateActions();
    }

    toggleSelection(path) {
        if (this.selectedItems.has(path)) {
            this.selectedItems.delete(path);
        } else {
            this.selectedItems.add(path);
        }
        this.updateSelection();
        this.updateActions();
    }

    clearSelection() {
        this.selectedItems.clear();
        this.updateSelection();
        this.updateActions();
    }

    updateSelection() {
        if (!this.modal) return;
        UIComponents.updateSelection(this.modal, this.selectedItems);
    }

    updateActions() {
        if (!this.modal) return;
        UIComponents.updateActions(this.modal, this.selectedItems.size > 0);
    }

    updateItemCount() {
        if (!this.modal) return;
        UIComponents.updateItemCount(this.modal, this.currentContents.length);
    }

    showCreateFolderForm() {
        if (!this.modal || this.isCreatingFolder) return;
        
        this.isCreatingFolder = true;
        UIComponents.showCreateFolderForm(this.modal);
    }

    hideCreateFolderForm() {
        if (!this.modal) return;
        
        this.isCreatingFolder = false;
        UIComponents.hideCreateFolderForm(this.modal);
    }

    async createFolder() {
        if (!this.modal || !this.isCreatingFolder) return;
        
        UIComponents.showMessage(this.modal, ''); // Clear previous messages
        const input = this.modal.querySelector('#fs-folder-name');
        const folderName = input.value.trim();
        
        if (!folderName) {
            UIComponents.showMessage(this.modal, 'Please enter a folder name', true);
            return;
        }
        
        try {
            const response = await api.fetchApi('/filesystem/create_directory', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path: this.currentPath,
                    directory_name: folderName
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showMessage(this.modal, result.message, false);
                this.hideCreateFolderForm();
                // Ensure refresh happens after folder creation
                await this.refreshCurrentDirectory();
            } else {
                UIComponents.showMessage(this.modal, result.error, true);
            }
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error creating folder: ${error.message}`, true);
        }
    }

    async deleteSelected() {
        if (this.selectedItems.size === 0) return;
        
        UIComponents.showMessage(this.modal, ''); // Clear previous messages
        const itemCount = this.selectedItems.size;
        const confirmMessage = `Are you sure you want to delete ${itemCount} item${itemCount !== 1 ? 's' : ''}? This action cannot be undone.`;
        
        const result = await Dialog.show({
            title: "Confirm Delete",
            message: confirmMessage,
            buttons: ["Cancel", "Delete"],
            defaultButton: 0,
            type: 'danger'
        });
        
        if (result !== 1) return;
        
        try {
            let successCount = 0;
            let errors = [];
            
            for (const path of this.selectedItems) {
                const response = await api.fetchApi('/filesystem/delete', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        path: path
                    })
                });
                
                const deleteResult = await response.json();
                
                if (deleteResult.success) {
                    successCount++;
                } else {
                    errors.push(`${path}: ${deleteResult.error}`);
                }
            }
            
            if (successCount > 0) {
                UIComponents.showMessage(this.modal, `${successCount} item${successCount !== 1 ? 's' : ''} deleted successfully`, false);
            }
            
            if (errors.length > 0) {
                UIComponents.showMessage(this.modal, `Errors: ${errors.join(', ')}`, true);
            }
            
            this.clearSelection();
            // Ensure refresh happens after deletion
            await this.refreshCurrentDirectory();
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error deleting items: ${error.message}`, true);
            // Refresh even on error to ensure view is consistent
            await this.refreshCurrentDirectory();
        }
    }

    async startUpload() {
        if (!this.uploadModal) return;
        
        UIComponents.showUploadMessage(this.uploadModal, '', false); // Clear previous messages
        UIComponents.showUploadProgress(this.uploadModal, 'Starting...', 0);

        const url = this.uploadModal.querySelector('#fs-upload-url').value.trim();
        
        if (!url) {
            // UIComponents.showMessage(this.modal, 'Please enter a upload URL', true); // Show message in main modal
            UIComponents.showUploadMessage(this.uploadModal, 'Please enter an upload URL.', true);
            UIComponents.hideUploadProgress(this.uploadModal);
            return;
        }
        
        // Get upload type from current form title or a data attribute
        const formTitleElement = this.uploadModal.querySelector('#fs-upload-form-title');
        const title = formTitleElement ? formTitleElement.textContent : '';
        let uploadType = 'direct-link'; // Default
        
        if (title.includes('Google Drive')) uploadType = 'google-drive';
        else if (title.includes('Hugging Face')) uploadType = 'huggingface';
        else if (title.includes('Civitai')) uploadType = 'civitai';
        
        this.currentUploadType = uploadType; // Store for progress polling
        const sessionId = 'upload_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this.currentUploadSessionId = sessionId;

        const uploadData = {
            url: url,
            path: this.currentPath, // Destination path in FSM
            session_id: sessionId
        };

        let apiEndpoint = '/filesystem/upload'; // Default endpoint

        if (uploadType === 'google-drive') {
            apiEndpoint = '/filesystem/upload_from_google_drive';
            const filename = this.uploadModal.querySelector('#fs-gdrive-filename').value.trim();
            const extension = this.uploadModal.querySelector('#fs-gdrive-extension').value.trim();
            
            if (!filename || !extension) {
                UIComponents.showUploadMessage(this.uploadModal, 'Filename and extension are required for Google Drive uploads.', true);
                UIComponents.hideUploadProgress(this.uploadModal);
                return;
            }
            uploadData.filename = filename;
            uploadData.extension = extension;
            uploadData.google_drive_url = url; // The endpoint expects 'google_drive_url'
            delete uploadData.url; // Remove generic 'url' if specific one is used
            uploadData.overwrite = this.uploadModal.querySelector('#fs-gdrive-overwrite').checked;
            uploadData.auto_extract_zip = this.uploadModal.querySelector('#fs-gdrive-auto-extract').checked;
        } else {
            // For other types, you might have a generic filename input
            const commonFilenameInput = this.uploadModal.querySelector('#fs-upload-filename');
            if (commonFilenameInput) {
                 uploadData.filename = commonFilenameInput.value.trim();
            }
            // Add type-specific fields for Hugging Face, Civitai, etc.
            if (uploadType === 'huggingface') {
                const token = this.uploadModal.querySelector('#fs-hf-token')?.value.trim();
                if (token) uploadData.token = token;
            } else if (uploadType === 'civitai') {
                const token = this.uploadModal.querySelector('#fs-civitai-token')?.value.trim();
                if (token) uploadData.token = token;
            }
        }
        
        try {
            this.startUploadProgressPolling(sessionId, uploadType);

            const response = await api.fetchApi(apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(uploadData)
            });
            
            // The actual result processing will be handled by the poller for GDrive
            // For other uploads, it might be direct.
            // For now, assume GDrive is primary focus for polling.
            if (uploadType !== 'google-drive') {
                const result = await response.json();
                this.stopUploadProgressPolling();
                if (result.success) {
                    UIComponents.showUploadMessage(this.uploadModal, result.message || 'Upload started successfully.', false);
                    // UIComponents.showMessage(this.modal, result.message || 'Upload started successfully.', false);
                    // this.closeUploadModal(); // Close only on clear success for non-polling types
                    await this.refreshCurrentDirectory();
                } else {
                    UIComponents.showUploadMessage(this.uploadModal, result.error || 'Upload failed.', true);
                    // UIComponents.showMessage(this.modal, result.error || 'Upload failed.', true);
                }
                 UIComponents.hideUploadProgress(this.uploadModal);
            } else {
                // For Google Drive, the initial response might just acknowledge the request.
                // The poller will handle the final messages.
                // If the initial request itself fails (e.g. 400 error), handle it.
                if (!response.ok) {
                    const errorResult = await response.json();
                    this.stopUploadProgressPolling();
                    UIComponents.showUploadMessage(this.uploadModal, errorResult.error || `Request failed: ${response.statusText}`, true);
                    UIComponents.hideUploadProgress(this.uploadModal);
                }
            }

        } catch (error) {
            this.stopUploadProgressPolling();
            UIComponents.showUploadMessage(this.uploadModal, `Error starting upload: ${error.message}`, true);
            // UIComponents.showMessage(this.modal, `Error starting upload: ${error.message}`, true);
            UIComponents.hideUploadProgress(this.uploadModal);
        }
    }


    startUploadProgressPolling(sessionId, uploadType) {
        if (this.uploadProgressInterval) {
            clearInterval(this.uploadProgressInterval);
        }
        // Only poll for Google Drive for now, others might be quick or use different mechanism
        if (uploadType !== 'google-drive') return;

        this.uploadProgressInterval = setInterval(async () => {
            if (!this.uploadModal || !this.currentUploadSessionId) {
                this.stopUploadProgressPolling();
                return;
            }
            try {
                const progressResponse = await api.fetchApi(`/filesystem/google_drive_progress/${this.currentUploadSessionId}`);
                const progress = await progressResponse.json();

                UIComponents.showUploadProgress(this.uploadModal, progress.message, progress.percentage);

                if (progress.status === 'completed' || progress.status === 'error') {
                    this.stopUploadProgressPolling();
                    if (progress.status === 'completed') {
                        UIComponents.showUploadMessage(this.uploadModal, `✅ ${progress.message}`, false);
                        await this.refreshCurrentDirectory();
                        // Optionally close modal after a delay or provide a "Done" button
                        // setTimeout(() => this.closeUploadModal(), 2000); 
                    } else { // error or not_found after trying
                        UIComponents.showUploadMessage(this.uploadModal, `❌ ${progress.message || 'An error occurred.'}`, true);
                    }
                }
            } catch (err) {
                console.error('Error polling upload progress:', err);
                UIComponents.showUploadMessage(this.uploadModal, 'Error checking progress.', true);
                this.stopUploadProgressPolling(); // Stop if polling fails
            }
        }, 1000); // Poll every 1 second
    }

    stopUploadProgressPolling() {
        if (this.uploadProgressInterval) {
            clearInterval(this.uploadProgressInterval);
            this.uploadProgressInterval = null;
        }
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
    }

    async downloadSelected() {
        if (this.selectedItems.size === 0) return;
        
        try {
            // Filter only files (not directories)
            const filesToDownload = this.currentContents.filter(item => 
                this.selectedItems.has(item.path) && item.type === 'file'
            );
            
            if (filesToDownload.length === 0) {
                UIComponents.showMessage(this.modal, 'No files selected for download. Only files can be downloaded.', true);
                return;
            }
            
            if (filesToDownload.length === 1) {
                // Single file download
                await this.downloadSingleFile(filesToDownload[0].path);
            } else {
                // Multiple files - create zip and download
                await this.downloadMultipleFiles(filesToDownload.map(f => f.path));
            }
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error downloading files: ${error.message}`, true);
        }
    }
    
    async downloadSingleFile(filePath) {
        try {
            UIComponents.showStatus(this.modal, 'Preparing download...');
            
            const response = await api.fetchApi(`/filesystem/download_file?path=${encodeURIComponent(filePath)}`);
            
            if (!response.ok) {
                let errorMessage = 'Download failed';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }
            
            // Get filename from Content-Disposition header or path
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = filePath.split('/').pop();
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            // Create blob and download
            const blob = await response.blob();
            this.triggerBrowserDownload(blob, filename);
            
            UIComponents.showMessage(this.modal, `File "${filename}" downloaded successfully`, false);
            UIComponents.showStatus(this.modal, 'Ready');
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error downloading file: ${error.message}`, true);
            UIComponents.showStatus(this.modal, 'Ready');
        }
    }
    
    async downloadMultipleFiles(filePaths) {
        try {
            UIComponents.showStatus(this.modal, 'Creating archive...');
            
            const response = await api.fetchApi('/filesystem/download_multiple', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    paths: filePaths
                })
            });
            
            if (!response.ok) {
                let errorMessage = 'Archive creation failed';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.error || errorMessage;
                } catch {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }
            
            // Get archive filename
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'files.zip';
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            // Create blob and download
            const blob = await response.blob();
            this.triggerBrowserDownload(blob, filename);
            
            UIComponents.showMessage(this.modal, `Archive "${filename}" with ${filePaths.length} files downloaded successfully`, false);
            UIComponents.showStatus(this.modal, 'Ready');
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error creating archive: ${error.message}`, true);
            UIComponents.showStatus(this.modal, 'Ready');
        }
    }
    
    triggerBrowserDownload(blob, filename) {
        // Create a temporary URL for the blob
        const url = window.URL.createObjectURL(blob);
        
        // Create a temporary anchor element and trigger download
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.style.display = 'none';
        
        document.body.appendChild(a);
        a.click();
        
        // Clean up
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    async refreshCurrentDirectory() {
        await this.navigateToPath(this.currentPath);
    }
}
