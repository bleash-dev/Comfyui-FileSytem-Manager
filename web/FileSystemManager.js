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
        this.isRenamingItem = false;
        this.uploadProgressInterval = null;
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
        this.activeContextMenu = { itemPath: null, element: null };
        this.boundHandleDocumentClick = this.handleDocumentClick.bind(this);
        this.globalModelsStructure = null;
        this.downloadProgress = {};
        this.workflowMonitor = {
            enabled: true,
            autoDownload: true,
            lastAnalysis: null
        };
        this.missingModelsHandler = null;
        
        this.globalModelsMonitoringInterval = null; // For global model progress
        this.workflowMonitoringInterval = null;    // For workflow changes
        this.progressPollingInterval = null;       // For individual file uploads/downloads
        this.activeDownloads = new Set();

        this.setupMissingModelsHandler();
        // Monitoring will be started when the modal is shown or globally as needed
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
        modal.querySelector('#fs-rename').addEventListener('click', () => this.showRenameForm());
        modal.querySelector('#fs-delete').addEventListener('click', () => this.deleteSelected());
        modal.querySelector('#fs-refresh').addEventListener('click', () => this.refreshCurrentDirectory());
        
        // Create folder form
        modal.querySelector('#fs-create-confirm').addEventListener('click', () => this.createFolder());
        modal.querySelector('#fs-create-cancel').addEventListener('click', () => this.hideCreateFolderForm());
        modal.querySelector('#fs-folder-name').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.createFolder();
            if (e.key === 'Escape') this.hideCreateFolderForm();
        });

        // Rename item form
        modal.querySelector('#fs-rename-confirm').addEventListener('click', () => this.confirmRename());
        modal.querySelector('#fs-rename-cancel').addEventListener('click', () => this.hideRenameForm());
        modal.querySelector('#fs-new-name').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.confirmRename();
            if (e.key === 'Escape') this.hideRenameForm();
        });
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });

        // Add ESC key handler
        this.handleKeyDown = (e) => {
            if (e.key === 'Escape' && this.modal) {
                this.closeModal();
            }
        };
        
        document.addEventListener('keydown', this.handleKeyDown);

         modal.addEventListener('globalModelCancel', (e) => {
            this.cancelGlobalModelDownload(e.detail.modelPath);
        });
        
        modal.addEventListener('globalModelDownloaded', (e) => {
            if (this.modal) { // Check if modal is active
                this.refreshCurrentDirectory();
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
        // Check if there are active downloads and prevent closing
        if (this.hasActiveDownloads()) {
            this.showNotificationMessage('Cannot close while downloads are in progress. Please wait for downloads to complete or cancel them first.', true);
            return;
        }
        
        if (this.uploadModal) {
            if (this.uploadModal.parentNode === document.body) { // Check if it's still in the DOM
                document.body.removeChild(this.uploadModal);
            }
            this.uploadModal = null;
        }
        
        // Clean up upload modal ESC key handler
        if (this.handleUploadKeyDown) {
            document.removeEventListener('keydown', this.handleUploadKeyDown);
            this.handleUploadKeyDown = null;
        }
        
        this.stopUploadProgressPolling();
        
        // Clear activeDownloads when closing upload modal
        this.activeDownloads.clear();
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
    }

    setUploadButtonState(enabled) {
        if (this.uploadModal) {
            const uploadButton = this.uploadModal.querySelector('#fs-upload-start');
            if (uploadButton) {
                uploadButton.disabled = !enabled;
            }
        }
    }

    handleUploadFormInputChange() {
        this.setUploadButtonState(true);
    }

    setupUploadEventListeners(modal) {
        // Close upload modal
        modal.querySelector('#fs-upload-close').addEventListener('click', () => this.closeUploadModal());
        
        // Upload option selection
        modal.querySelectorAll('.fs-upload-option').forEach(option => {
            option.addEventListener('click', () => {
                const type = option.dataset.type;
                this.currentUploadType = type;
                let destinationPathText

                if (this.selectedItems.size === 1) {
                    const selectedPath = Array.from(this.selectedItems)[0];
                    const selectedItem = this.currentContents.find(item => item.path === selectedPath);
                    if (selectedItem && selectedItem.type === 'directory') {
                        destinationPathText = selectedItem.path;
                    }
                }
                this.currentUploadDestinationPath = destinationPathText === "FSM Root" ? "" : destinationPathText;

                UIComponents.showUploadForm(modal, type, destinationPathText);
                this.setUploadButtonState(true);
                this.attachUploadFormInputListeners(modal);
            });
        });
        
        // Back button
        modal.querySelector('#fs-upload-back').addEventListener('click', () => {
            UIComponents.showUploadOptions(modal);
        });
        
        // Upload actions
        modal.querySelector('#fs-upload-start').addEventListener('click', () => this.startUpload());
        modal.querySelector('#fs-upload-cancel').addEventListener('click', () => this.closeUploadModal());
        
        modal.addEventListener('uploadCancel', () => this.cancelUpload());
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeUploadModal();
            }
        });

        // Add ESC key handler for upload modal
        this.handleUploadKeyDown = (e) => {
            if (e.key === 'Escape' && this.uploadModal) {
                this.closeUploadModal();
            }
        };
        
        document.addEventListener('keydown', this.handleUploadKeyDown);
    }

    attachUploadFormInputListeners(modal) {
        if (!modal) return;
        const formContent = modal.querySelector('.fs-upload-form-content');
        if (!formContent) return;

        const inputs = formContent.querySelectorAll('input[type="text"], input[type="password"], input[type="checkbox"]');
        
        this.boundHandleUploadFormInputChange = this.boundHandleUploadFormInputChange || this.handleUploadFormInputChange.bind(this);
        this.boundHandleGdriveFieldValidation = this.boundHandleGdriveFieldValidation || this.handleGdriveFieldValidation.bind(this);

        inputs.forEach(input => {
            input.removeEventListener('input', this.boundHandleUploadFormInputChange);
            input.removeEventListener('change', this.boundHandleUploadFormInputChange);
            input.removeEventListener('blur', this.boundHandleGdriveFieldValidation);

            if (input.type === 'checkbox') {
                input.addEventListener('change', this.boundHandleUploadFormInputChange);
            } else {
                input.addEventListener('input', this.boundHandleUploadFormInputChange);
            }

            if (this.currentUploadType === 'google-drive' && (input.id === 'fs-gdrive-filename' || input.id === 'fs-gdrive-extension')) {
                input.addEventListener('blur', this.boundHandleGdriveFieldValidation);
                input.addEventListener('input', (e) => {
                    if (e.target.value.trim() !== '') {
                        e.target.classList.remove('fs-input-error');
                    }
                });
            }
        });
    }

    handleGdriveFieldValidation(event) {
        const input = event.target;
        if (input.value.trim() === '') {
            input.classList.add('fs-input-error');
        } else {
            input.classList.remove('fs-input-error');
        }
    }

    async showModal() {
        if (this.modal) {
            this.closeModal(); // Should properly clean up old modal and intervals
        }
        
        this.modal = this.createModal();
        document.body.appendChild(this.modal);
        
        await this.navigateToPath('');
        this.boundHandleUploadFormInputChange = this.handleUploadFormInputChange.bind(this);

        // Start monitoring relevant to this modal instance
        this.startGlobalModelsMonitoring();
        this.startWorkflowMonitoring(); // If it's tied to the FSM instance lifecycle
    }

    closeModal() {
        // Check if there are active downloads and prevent closing
        if (this.hasActiveDownloads()) {
            this.showNotificationMessage('Cannot close while downloads are in progress. Please wait for downloads to complete or cancel them first.', true);
            return;
        }
        
        if (this.modal) {
            if (this.modal.parentNode === document.body) { // Check if it's still in the DOM
                 document.body.removeChild(this.modal);
            }
            this.modal = null;
        }
        
        // Clean up ESC key handler
        if (this.handleKeyDown) {
            document.removeEventListener('keydown', this.handleKeyDown);
            this.handleKeyDown = null;
        }
        
        this.closeActiveContextMenu();
        if (this.uploadModal) {
            this.closeUploadModal();
        }

        // Stop monitoring relevant to this modal instance
        this.stopGlobalModelsMonitoring();
        this.stopWorkflowMonitoring(); // If it's tied to the FSM instance lifecycle

        this.currentPath = '';
        this.selectedItems = new Set();
        this.currentContents = [];
        this.isCreatingFolder = false;
        this.isRenamingItem = false;
        this.uploadProgressInterval = null; // This one is for specific uploads, handled by its own stop method
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
        this.activeContextMenu = { itemPath: null, element: null };
        
        // Remove ESC key handler
        document.removeEventListener('keydown', this.handleKeyDown);
    }

    /**
     * Check if a file is currently being downloaded
     */
    isFileBeingDownloaded(item) {
        // Check if there's an active upload session that could be downloading to this file's location
        if (this.currentUploadSessionId && this.currentUploadType) {
            return true; // If there's any active download session, be cautious
        }
        
        // Check if the file path is in active downloads
        return this.activeDownloads.has(item.path);
    }

    /**
     * Check if there are any active downloads in progress
     */
    hasActiveDownloads() {
        return this.currentUploadSessionId !== null || this.activeDownloads.size > 0 && !this.downloadError;
    }

    updateBreadcrumb() {
        if (!this.modal) return;
        UIComponents.updateBreadcrumb(this.modal, this.currentPath, (path) => this.navigateToPath(path));
    }

    async navigateToPath(path) {
        if (!this.modal && path !== '') { // Allow initial load if modal not yet fully set, but not subsequent navigations
            console.warn("Attempted to navigate without an active modal to path:", path);
            return;
        }
        try {
            this.closeActiveContextMenu();
            if (this.currentPath !== path) {
                this.selectedItems.clear();
            }
            if (this.modal) UIComponents.showStatus(this.modal, 'Loading...');
            
            const response = await api.fetchApi(`/filesystem/browse?path=${encodeURIComponent(path)}`);
            const result = await response.json();
            
            if (result.success) {
                this.currentPath = path;
                this.currentContents = result.contents;
                this.selectedItems.clear();
                if (this.modal) { // Only update UI if modal exists
                    this.updateBreadcrumb();
                    this.renderContents();
                    this.updateActions();
                    UIComponents.showStatus(this.modal, 'Ready');
                }
            } else {
                if (this.modal) {
                    UIComponents.showMessage(this.modal, result.error, true);
                    UIComponents.showStatus(this.modal, 'Error');
                }
            }
        } catch (error) {
            console.error('Navigation error:', error);
            if (this.modal) {
                UIComponents.showMessage(this.modal, `Error loading directory: ${error.message}`, true);
                UIComponents.showStatus(this.modal, 'Error');
            }
        }
    }

    renderContents() {
        if (!this.modal) return;
        
        UIComponents.renderContents(
            this.modal,
            this.currentContents,
            (item, e) => this.handleItemClick(item, e),
            (path) => this.navigateToPath(path),
            (item, triggerElement) => this.showItemContextMenu(item, triggerElement),
            (item) => this.handleGlobalModelDownload(item)
        );
        
        this.updateItemCount();
        this.attachNavigationHandlers();
    }

    attachNavigationHandlers() {
        if (!this.modal) return;
        
        const directoryLinks = this.modal.querySelectorAll('.fs-item-name-link[data-type="directory"]');
        directoryLinks.forEach(link => {
            link.removeEventListener('click', this.handleDirectoryLinkClick); // Assuming handleDirectoryLinkClick exists or is a placeholder
            link.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const path = link.dataset.path;
                if (path !== undefined) { // Check if path is defined
                    this.navigateToPath(path);
                }
            });
        });
    }
    // Placeholder if you had a specific named handler before
    handleDirectoryLinkClick(e) { 
      // This function can be empty if the anonymous function in attachNavigationHandlers is sufficient
      // Or it can contain the logic if you prefer a named handler
        e.preventDefault();
        e.stopPropagation();
        const path = e.currentTarget.dataset.path;
        if (path !== undefined) {
            this.navigateToPath(path);
        }
    }


    handleItemClick(item, e) {
        this.closeActiveContextMenu();
        const itemPath = item.path;
        const isNameLinkClicked = e.target.closest('.fs-item-name-link');

        if (isNameLinkClicked && item.type === 'directory') {
            e.preventDefault();
            e.stopPropagation();
            this.navigateToPath(itemPath);
            return;
        }

        if (e.ctrlKey || e.metaKey) {
            this.toggleSelection(itemPath);
        } else {
            this.selectItem(itemPath);
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

    closeActiveContextMenu() {
        if (this.activeContextMenu.element) {
            if (this.activeContextMenu.element.parentNode) {
                this.activeContextMenu.element.remove();
            }
            this.activeContextMenu = { itemPath: null, element: null };
            document.removeEventListener('click', this.boundHandleDocumentClick, true);
        }
    }

    handleDocumentClick(event) {
        if (this.activeContextMenu.element && !this.activeContextMenu.element.contains(event.target)) {
            const trigger = event.target.closest('.fs-item-actions-trigger');
            if (trigger) {
                const row = trigger.closest('tr');
                if (row && row.dataset.path === this.activeContextMenu.itemPath) {
                    return;
                }
            }
            this.closeActiveContextMenu();
        }
    }

    showItemContextMenu(item, triggerElement) {
        this.closeActiveContextMenu(); 

        this.activeContextMenu.itemPath = item.path;

        const actions = [];
        
        // Symlinks have limited actions
        if (item.is_symlink) {
            // Only allow deletion for symlinks
            actions.push({ id: 'delete', label: 'Delete Symlink', icon: '🗑️' });
        } else {
            actions.push({ id: 'rename', label: 'Rename', icon: '✏️' });
            if (item.type === 'file') {
                actions.push({ id: 'download', label: 'Download', icon: '⬇️' });
                
                // Add symlink option for files in models directory that are fully downloaded
                if (item.path.startsWith('models/') && item.local_exists && !this.isFileBeingDownloaded(item)) {
                    actions.push({ id: 'create_symlink', label: 'Create Symlink', icon: '🔗' });
                }
            }
            actions.push({ id: 'delete', label: 'Delete', icon: '🗑️' });
        }

        const menu = UIComponents.createItemContextMenu(actions, (actionId) => {
            this.handleContextMenuAction(actionId, item);
        });
        
        this.activeContextMenu.element = menu;
        if (!this.modal) return; // Guard against modal being null
        const modalContentRect = this.modal.querySelector('.fs-modal-content').getBoundingClientRect();
        const triggerRect = triggerElement.getBoundingClientRect();
        
        document.body.appendChild(menu);

        menu.style.top = `${triggerRect.bottom}px`;
        menu.style.left = `${triggerRect.left}px`;

        const menuRect = menu.getBoundingClientRect();
        if (menuRect.right > window.innerWidth - 10) {
            menu.style.left = `${triggerRect.right - menuRect.width}px`;
        }
        if (menuRect.bottom > window.innerHeight - 10) {
            menu.style.top = `${triggerRect.top - menuRect.height}px`;
        }
        
        setTimeout(() => {
            document.addEventListener('click', this.boundHandleDocumentClick, true);
        }, 0);
    }

    async handleContextMenuAction(actionId, item) {
        this.closeActiveContextMenu(); 
        
        switch (actionId) {
            case 'rename':
                this.showRenameFormForItem(item);
                break;
            case 'delete':
                await this.deleteSingleItem(item);
                break;
            case 'download':
                if (item.type === 'file') {
                    await this.downloadSingleFile(item.path);
                }
                break;
            case 'create_symlink':
                await this.showSymlinkDialog(item);
                break;
            default:
                console.warn('Unknown context menu action:', actionId);
        }
    }
    
    showRenameFormForItem(item) {
        this.selectedItems.clear();
        this.selectedItems.add(item.path);
        this.updateSelection(); 
        this.updateActions();   
        this.showRenameForm();
    }

    async deleteSingleItem(item) {
        if (!this.modal) return;
        UIComponents.showMessage(this.modal, ''); 
        
        // Check if this is a file that might have symlinks pointing to it
        let confirmMessage = `Are you sure you want to delete "${item.name}"? This action cannot be undone.`;
        
        // Add warning for non-symlink files that might have symlinks pointing to them
        if (item.type === 'file' && !item.is_symlink) {
            confirmMessage += '\n\nNote: If any symlinks point to this file, they will also be deleted automatically.';
        }
        
        const result = await Dialog.show({
            title: "Confirm Delete",
            message: confirmMessage,
            buttons: ["Cancel", "Delete"],
            defaultButton: 0,
            type: 'danger'
        });
        
        if (result !== 1) return;

        try {
            const response = await api.fetchApi('/filesystem/delete', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: item.path })
            });
            const deleteResult = await response.json();

            if (deleteResult.success) {
                UIComponents.showMessage(this.modal, deleteResult.message, false);
            } else {
                UIComponents.showMessage(this.modal, deleteResult.error, true);
            }
            await this.refreshCurrentDirectory();
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error deleting item: ${error.message}`, true);
            await this.refreshCurrentDirectory();
        }
    }

    updateActions() {
        if (!this.modal) return;
        UIComponents.updateActions(this.modal, this.selectedItems.size > 0); 
        
        const renameBtn = this.modal.querySelector('#fs-rename');
        const uploadBtn = this.modal.querySelector('#fs-upload');
        const createFolderBtn = this.modal.querySelector('#fs-create-folder');
        const downloadSelectedBtn = this.modal.querySelector('#fs-download-selected');

        if (renameBtn) {
            renameBtn.disabled = this.selectedItems.size !== 1;
        }

        if (downloadSelectedBtn) {
            let canDownloadSelected = false;
            if (this.selectedItems.size > 0) {
                for (const path of this.selectedItems) {
                    const item = this.currentContents.find(contentItem => contentItem.path === path);
                    if (item && item.type === 'file') {
                        canDownloadSelected = true;
                        break;
                    }
                }
            }
            downloadSelectedBtn.disabled = !canDownloadSelected;
        }

        let canUpload = false;
        let canCreateFolder = false;

        if (this.selectedItems.size === 0) {
            canUpload = true; 
            canCreateFolder = true;
        } else if (this.selectedItems.size === 1) {
            const selectedPath = Array.from(this.selectedItems)[0];
            const selectedItem = this.currentContents.find(item => item.path === selectedPath);
            if (selectedItem && selectedItem.type === 'directory') {
                canUpload = true;
                canCreateFolder = true;
            }
        }

        if (uploadBtn) {
            uploadBtn.disabled = !canUpload;
        }
        if (createFolderBtn) {
            createFolderBtn.disabled = !canCreateFolder;
        }
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

    showRenameForm() {
        if (!this.modal || this.isRenamingItem || this.selectedItems.size !== 1) return;

        this.isRenamingItem = true;
        this.hideCreateFolderForm();

        const selectedPath = Array.from(this.selectedItems)[0];
        const currentName = selectedPath.split('/').pop();
        
        const form = this.modal.querySelector('#fs-rename-form');
        const input = this.modal.querySelector('#fs-new-name');
        
        input.value = currentName;
        form.style.display = 'flex';
        input.focus();
        input.select();
    }

    hideRenameForm() {
        if (!this.modal) return;
        this.isRenamingItem = false;
        const form = this.modal.querySelector('#fs-rename-form');
        form.style.display = 'none';
    }

    async confirmRename() {
        if (!this.modal || !this.isRenamingItem || this.selectedItems.size !== 1) return;

        UIComponents.showMessage(this.modal, '');
        const input = this.modal.querySelector('#fs-new-name');
        const newName = input.value.trim();
        const oldPath = Array.from(this.selectedItems)[0];

        if (!newName) {
            UIComponents.showMessage(this.modal, 'Please enter a new name', true);
            return;
        }
        
        if (newName === oldPath.split('/').pop()) {
            UIComponents.showMessage(this.modal, 'New name is the same as the old name.', false);
            this.hideRenameForm();
            return;
        }

        try {
            const response = await api.fetchApi('/filesystem/rename_item', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_path: oldPath, new_name: newName })
            });
            const result = await response.json();

            if (result.success) {
                UIComponents.showMessage(this.modal, result.message, false);
                this.hideRenameForm();
                this.selectedItems.clear(); 
                await this.refreshCurrentDirectory();
            } else {
                UIComponents.showMessage(this.modal, result.error, true);
            }
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error renaming item: ${error.message}`, true);
        }
    }

    async createFolder() {
        if (!this.modal || !this.isCreatingFolder) return;
        
        UIComponents.showMessage(this.modal, '');
        const input = this.modal.querySelector('#fs-folder-name');
        const folderName = input.value.trim();
        
        if (!folderName) {
            UIComponents.showMessage(this.modal, 'Please enter a folder name', true);
            return;
        }

        let targetPath = this.currentPath;
        if (this.selectedItems.size === 1) {
            const selectedPath = Array.from(this.selectedItems)[0];
            const selectedItem = this.currentContents.find(item => item.path === selectedPath);
            if (selectedItem && selectedItem.type === 'directory') {
                targetPath = selectedItem.path;
            }
        }
        
        try {
            const response = await api.fetchApi('/filesystem/create_directory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: targetPath, directory_name: folderName })
            });
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showMessage(this.modal, result.message, false);
                this.hideCreateFolderForm();
                await this.refreshCurrentDirectory();
            } else {
                UIComponents.showMessage(this.modal, result.error, true);
            }
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error creating folder: ${error.message}`, true);
        }
    }

    async deleteSelected() {
        if (this.selectedItems.size === 0 || !this.modal) return;
        
        UIComponents.showMessage(this.modal, '');
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
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });
                const deleteResult = await response.json();
                if (deleteResult.success) successCount++;
                else errors.push(`${path}: ${deleteResult.error}`);
            }
            
            if (successCount > 0) UIComponents.showMessage(this.modal, `${successCount} item${successCount !== 1 ? 's' : ''} deleted successfully`, false);
            if (errors.length > 0) UIComponents.showMessage(this.modal, `Errors: ${errors.join(', ')}`, true);
            
            this.clearSelection();
            await this.refreshCurrentDirectory();
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error deleting items: ${error.message}`, true);
            await this.refreshCurrentDirectory();
        }
    }

    async startUpload() {
        if (!this.uploadModal) return;
        
        this.setUploadButtonState(false);
        UIComponents.showUploadMessage(this.uploadModal, '', false); 

        const urlInput = this.uploadModal.querySelector('#fs-upload-url');
        const url = urlInput.value.trim();
        
        let hasError = false;
        const errors = [];

        urlInput.classList.remove('fs-input-error');
        if (!url) {
            errors.push('URL/Repo ID is required.');
            urlInput.classList.add('fs-input-error');
            hasError = true;
        }

        let backendDestinationPath = this.currentPath;
        if (this.currentUploadDestinationPath !== undefined) {
            backendDestinationPath = this.currentUploadDestinationPath;
        }

        const uploadData = { url: url, path: backendDestinationPath };
        let apiEndpoint = '/filesystem/upload';

        if (this.currentUploadType === 'google-drive') {
            apiEndpoint = '/filesystem/upload_from_google_drive';
            const filenameInput = this.uploadModal.querySelector('#fs-gdrive-filename');
            const extensionInput = this.uploadModal.querySelector('#fs-gdrive-extension');
            const filename = filenameInput.value.trim();
            let extension = extensionInput.value.trim();

            filenameInput.classList.remove('fs-input-error');
            extensionInput.classList.remove('fs-input-error');

            if (!filename) { errors.push('Filename is required for Google Drive.'); filenameInput.classList.add('fs-input-error'); hasError = true; }
            if (!extension) { errors.push('Extension is required for Google Drive.'); extensionInput.classList.add('fs-input-error'); hasError = true; }
            else {
                extension = extension.replace(/^\./, '');
                if (!extension) { errors.push('Extension cannot be empty or just a dot.'); extensionInput.classList.add('fs-input-error'); hasError = true; }
            }
            if (hasError) { 
                UIComponents.showUploadMessage(this.uploadModal, errors.join(' '), true); 
                this.downloadError = true; // Set error state to prevent further actions
                return; 
            }

            uploadData.filename = filename;
            uploadData.extension = extension;
            uploadData.google_drive_url = url; delete uploadData.url; 
            uploadData.overwrite = this.uploadModal.querySelector('#fs-gdrive-overwrite').checked;
            uploadData.auto_extract_zip = this.uploadModal.querySelector('#fs-gdrive-auto-extract').checked;

        } else if (this.currentUploadType === 'huggingface') {
            apiEndpoint = '/filesystem/download_from_huggingface';
            uploadData.hf_url = url; delete uploadData.url;
            uploadData.overwrite = this.uploadModal.querySelector('#fs-hf-overwrite').checked;
            const tokenInput = this.uploadModal.querySelector('#fs-hf-token');
            if (tokenInput && tokenInput.value.trim()) uploadData.user_token = tokenInput.value.trim();
        
        } else if (this.currentUploadType === 'civitai') {
            apiEndpoint = '/filesystem/download_from_civitai';
            uploadData.civitai_url = url; delete uploadData.url;
            uploadData.overwrite = this.uploadModal.querySelector('#fs-civitai-overwrite').checked;
            const tokenInput = this.uploadModal.querySelector('#fs-civitai-token');
            if (tokenInput && tokenInput.value.trim()) uploadData.user_token = tokenInput.value.trim();
            const filenameInput = this.uploadModal.querySelector('#fs-civitai-filename');
            if (filenameInput && filenameInput.value.trim()) uploadData.filename = filenameInput.value.trim();

        } else if (this.currentUploadType === 'direct-link') {
            apiEndpoint = '/filesystem/upload_from_direct_url';
            uploadData.direct_url = url; delete uploadData.url;
            uploadData.overwrite = this.uploadModal.querySelector('#fs-direct-overwrite').checked;
            const filenameInput = this.uploadModal.querySelector('#fs-direct-filename');
            if (filenameInput && filenameInput.value.trim()) uploadData.filename = filenameInput.value.trim();
        
        } else {
            if (hasError) { 
                UIComponents.showUploadMessage(this.uploadModal, errors.join(' '), true); 
                this.downloadError = true; // Set error state to prevent further actions
                return; 
            }
            const commonFilenameInput = this.uploadModal.querySelector('#fs-upload-filename');
            if (commonFilenameInput) uploadData.filename = commonFilenameInput.value.trim();
        }
        
        if (uploadData.path === "") {
            UIComponents.showUploadMessage(this.uploadModal, "Cannot upload to the root. Please select a sub-directory.", true);
            this.downloadError = true; // Set error state to prevent further actions
            this.setUploadButtonState(true);
            return;
        }

        UIComponents.showUploadProgress(this.uploadModal, 'Starting...', 0);
        const sessionId = 'upload_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this.currentUploadSessionId = sessionId;
        uploadData.session_id = sessionId;
        
        // Track this download in activeDownloads with the actual target file path
        let targetPath = uploadData.path;
        if (uploadData.filename) {
            targetPath = `${uploadData.path}/${uploadData.filename}`;
        } else {
            // For downloads without explicit filename, we'll track the directory
            targetPath = uploadData.path;
        }
        this.activeDownloads.add(targetPath);
        
        try {
            this.startUploadProgressPolling(sessionId, this.currentUploadType);
            this.downloadError = false; // Reset error state before starting upload
            const response = await api.fetchApi(apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(uploadData)
            });
            
            if (!response.ok) {
                const errorResult = await response.json();
                this.stopUploadProgressPolling();
                if (errorResult.error_type === 'access_restricted') {
                    UIComponents.showUploadMessage(this.uploadModal, errorResult.error, true, true);
                    this.downloadError = true; // Set error state to prevent further actions
                    if (this.currentUploadType === 'civitai') UIComponents.showCivitAITokenInput(this.uploadModal, true);
                    else UIComponents.showHFTokenInput(this.uploadModal, true);
                } else {
                    this.downloadError = true; // Set error state to prevent further actions
                    UIComponents.showUploadMessage(this.uploadModal, errorResult.error || `Request failed: ${response.statusText}`, true);
                }
                UIComponents.hideUploadProgress(this.uploadModal);
                this.setUploadButtonState(true);
                return;
            }

            if (['civitai', 'google-drive', 'huggingface', 'direct-link'].includes(this.currentUploadType)) {
                // Poller handles the rest
            } else {
                const result = await response.json();
                this.stopUploadProgressPolling();
                if (result.success) {
                    UIComponents.showUploadMessage(this.uploadModal, result.message || 'Upload started successfully.', false);
                    if (this.modal) await this.refreshCurrentDirectory(); // Check modal
                } else {
                    if (result.error_type === 'access_restricted') {
                        UIComponents.showUploadMessage(this.uploadModal, result.error, true, true);
                        this.downloadError = true; // Set error state to prevent further actions
                        UIComponents.showCivitAITokenInput(this.uploadModal, true);
                    } else {
                        UIComponents.showUploadMessage(this.uploadModal, result.error || 'Upload failed.', true);
                    }
                    this.setUploadButtonState(true);
                }
                UIComponents.hideUploadProgress(this.uploadModal); 
            }

        } catch (error) {
            this.stopUploadProgressPolling();
            UIComponents.showUploadMessage(this.uploadModal, `Error starting upload: ${error.message}`, true);
            this.downloadError = true; // Set error state to prevent further actions
            UIComponents.hideUploadProgress(this.uploadModal);
            this.setUploadButtonState(true);
        }
    }

    async cancelUpload() {
        if (!this.currentUploadSessionId || !this.uploadModal) return;
        
        try {
            UIComponents.showUploadMessage(this.uploadModal, 'Cancelling download...', false);

            const response = await api.fetchApi('/filesystem/cancel_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.currentUploadSessionId, download_type: this.currentUploadType })
            });
            const result = await response.json();
            
            if (result.success) UIComponents.showUploadMessage(this.uploadModal, 'Download cancelled successfully', false);
            else {
                 UIComponents.showUploadMessage(this.uploadModal, `Failed to cancel: ${result.error}`, true);
                this.downloadError = true; // Set error state to prevent further actions
            }
            
        } catch (error) {
            UIComponents.showUploadMessage(this.uploadModal, `Error cancelling download: ${error.message}`, true);
            this.downloadError = true; // Set error state to prevent further actions
        }
        
        // Clear activeDownloads when cancelling
        this.activeDownloads.clear();
        
        this.stopUploadProgressPolling();
        UIComponents.hideUploadProgress(this.uploadModal);
        this.setUploadButtonState(true);
    }

    startUploadProgressPolling(sessionId, uploadType) {
        this.stopUploadProgressPolling(); // Clear existing before starting new

        let progressApiEndpoint = null;
        if (['google-drive', 'huggingface', 'civitai', 'direct-link'].includes(uploadType)) {
            progressApiEndpoint = `/filesystem/${uploadType.replace('-', '_')}_progress/${sessionId}`;
        } else {
            return;
        }

        this.uploadProgressInterval = setInterval(async () => {
            if (!this.uploadModal || !this.currentUploadSessionId || this.currentUploadSessionId !== sessionId) {
                this.stopUploadProgressPolling(); // Stop if modal closed or session changed
                return;
            }
            try {
                const progressResponse = await api.fetchApi(progressApiEndpoint);
                const progress = await progressResponse.json();

                UIComponents.showUploadProgress(this.uploadModal, progress.message, progress.percentage);

                if (['completed', 'error', 'access_restricted', 'cancelled'].includes(progress.status)) {
                    this.stopUploadProgressPolling();
                    
                    // Clear the download from activeDownloads when finished
                    this.activeDownloads.clear();
                    
                    if (progress.status === 'completed') {
                        UIComponents.showUploadMessage(this.uploadModal, `✅ ${progress.message}`, false);
                        this.setUploadButtonState(false);
                        if (this.modal) await this.refreshCurrentDirectory(); // Check modal
                    } else if (progress.status === 'cancelled') {
                        UIComponents.showUploadMessage(this.uploadModal, `🚫 ${progress.message}`, false);
                        this.setUploadButtonState(true);
                        this.activeDownloads.clear(); // Clear active downloads on cancel
                    } else if (progress.status === 'access_restricted') {
                        UIComponents.showUploadMessage(this.uploadModal, progress.message, true, true);
                        this.activeDownloads.clear(); // Clear active downloads on access restricted
                        if (uploadType === 'civitai') UIComponents.showCivitAITokenInput(this.uploadModal, true);
                        else UIComponents.showHFTokenInput(this.uploadModal, true);
                        this.setUploadButtonState(true);
                    } else { 
                        UIComponents.showUploadMessage(this.uploadModal, `❌ ${progress.message || 'An error occurred.'}`, true);
                        this.setUploadButtonState(true);
                        this.downloadError = true; // Set error state to prevent further actions
                    }
                }
            } catch (err) {
                console.error('Error polling upload progress:', err);
                UIComponents.showUploadMessage(this.uploadModal, 'Error checking progress.', true);
                this.downloadError = true; // Set error state to prevent further actions
                this.setUploadButtonState(true);
                this.stopUploadProgressPolling();
            }
        }, 500);
    }

    stopUploadProgressPolling() {
        if (this.uploadProgressInterval) {
            clearInterval(this.uploadProgressInterval);
            this.uploadProgressInterval = null;
        }
        // Don't nullify currentUploadSessionId/Type here if polling might restart for the same session
        // Only nullify them when the upload is truly finished or modal closed
    }

    async downloadSelected() {
        if (this.selectedItems.size === 0 || !this.modal) return;
        
        try {
            const filesToDownload = this.currentContents.filter(item => 
                this.selectedItems.has(item.path) && item.type === 'file'
            );
            
            if (filesToDownload.length === 0) {
                UIComponents.showMessage(this.modal, 'No files selected for download.', true);
                return;
            }
            
            if (filesToDownload.length === 1) await this.downloadSingleFile(filesToDownload[0].path);
            else await this.downloadMultipleFiles(filesToDownload.map(f => f.path));
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error downloading files: ${error.message}`, true);
        }
    }
    
    async downloadSingleFile(filePath) {
        if (!this.modal) return;
        try {
            UIComponents.showStatus(this.modal, 'Preparing download...');
            const response = await api.fetchApi(`/filesystem/download_file?path=${encodeURIComponent(filePath)}`);
            
            if (!response.ok) {
                let errorMessage = 'Download failed'; try { const errorData = await response.json(); errorMessage = errorData.error || errorMessage; } catch { errorMessage = `HTTP ${response.status}: ${response.statusText}`; } throw new Error(errorMessage);
            }
            
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = filePath.split('/').pop();
            if (contentDisposition) { const m = contentDisposition.match(/filename="(.+)"/); if (m) filename = m[1]; }
            
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
        if (!this.modal) return;
        try {
            UIComponents.showStatus(this.modal, 'Creating archive...');
            const response = await api.fetchApi('/filesystem/download_multiple', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ paths: filePaths })
            });
            
            if (!response.ok) {
                let errorMessage = 'Archive creation failed'; try { const errorData = await response.json(); errorMessage = errorData.error || errorMessage; } catch { errorMessage = `HTTP ${response.status}: ${response.statusText}`; } throw new Error(errorMessage);
            }
            
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'files.zip';
            if (contentDisposition) { const m = contentDisposition.match(/filename="(.+)"/); if (m) filename = m[1]; }
            
            const blob = await response.blob();
            this.triggerBrowserDownload(blob, filename);
            UIComponents.showMessage(this.modal, `Archive "${filename}" downloaded`, false);
            UIComponents.showStatus(this.modal, 'Ready');
            
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error creating archive: ${error.message}`, true);
            UIComponents.showStatus(this.modal, 'Ready');
        }
    }
    
    triggerBrowserDownload(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename; a.style.display = 'none';
        document.body.appendChild(a); a.click();
        document.body.removeChild(a); window.URL.revokeObjectURL(url);
    }

    async refreshCurrentDirectory() {
        // Only refresh if the modal is supposed to be active (currentPath might be set even if modal is closed)
        if (this.modal) { 
            await this.navigateToPath(this.currentPath);
        }
    }

    async showSymlinkDialog(sourceItem) {
        if (!this.modal) return;
        
        // Check if the source file is fully downloaded and available
        if (!sourceItem.local_exists) {
            this.showNotificationMessage('Cannot create symlink: Source file does not exist locally.', true);
            return;
        }
        
        // Check if the source file is currently being downloaded
        if (this.isFileBeingDownloaded(sourceItem)) {
            this.showNotificationMessage('Cannot create symlink: Source file is currently being downloaded. Please wait for the download to complete.', true);
            return;
        }
        
        // Create symlink dialog
        const dialog = document.createElement('div');
        dialog.className = 'fs-symlink-dialog-overlay';
        
        dialog.innerHTML = `
            <div class="fs-symlink-dialog">
                <div class="fs-symlink-header">
                    <h3>Create Symlink</h3>
                    <button class="fs-symlink-close">×</button>
                </div>
                <div class="fs-symlink-content">
                    <div class="fs-symlink-source">
                        <label>Source File:</label>
                        <div class="fs-symlink-source-path">${sourceItem.name}</div>
                        <div class="fs-symlink-source-full">${sourceItem.path}</div>
                    </div>
                    <div class="fs-symlink-target">
                        <label>Target Directory:</label>
                        <div class="fs-symlink-browser">
                            <div class="fs-symlink-breadcrumb">
                                <span class="fs-breadcrumb-item" data-path="models">models</span>
                            </div>
                            <div class="fs-symlink-contents"></div>
                        </div>
                    </div>
                </div>
                <div class="fs-symlink-actions">
                    <button class="fs-symlink-cancel">Cancel</button>
                    <button class="fs-symlink-create" disabled>Create Symlink</button>
                </div>
            </div>
        `;
        
        // Add styles
        this.addSymlinkDialogStyles();
        
        // Add event listeners
        const closeBtn = dialog.querySelector('.fs-symlink-close');
        const cancelBtn = dialog.querySelector('.fs-symlink-cancel');
        const createBtn = dialog.querySelector('.fs-symlink-create');
        
        const closeDialog = () => {
            document.body.removeChild(dialog);
        };
        
        closeBtn.addEventListener('click', closeDialog);
        cancelBtn.addEventListener('click', closeDialog);
        createBtn.addEventListener('click', async () => {
            await this.createSymlink(sourceItem, this.selectedTargetPath);
            closeDialog();
        });
        
        // Close on backdrop click
        dialog.addEventListener('click', (e) => {
            if (e.target === dialog) closeDialog();
        });
        
        document.body.appendChild(dialog);
        
       
        this.selectedTargetPath = 'models';
        await this.loadSymlinkDirectoryContents('models', dialog);
    }

    async loadSymlinkDirectoryContents(path, dialog) {
        try {
            const response = await fetch(`/filesystem/browse?path=${encodeURIComponent(path)}`);
            const result = await response.json();
            
            if (!result.success) {
                throw new Error(result.error);
            }
            
            const contentsDiv = dialog.querySelector('.fs-symlink-contents');
            contentsDiv.innerHTML = '';
            
            // Filter to show only directories in models
            const directories = result.contents.filter(item => 
                item.type === 'directory' && 
                (item.local_exists || item.global_exists)
            );
            
            directories.forEach(item => {
                const dirItem = document.createElement('div');
                dirItem.className = 'fs-symlink-dir-item';
                dirItem.innerHTML = `
                    <span class="fs-symlink-dir-icon">📁</span>
                    <span class="fs-symlink-dir-name">${item.name}</span>
                `;
                
                dirItem.addEventListener('click', async () => {
                    // Remove selection from other items
                    contentsDiv.querySelectorAll('.fs-symlink-dir-item').forEach(el => 
                        el.classList.remove('selected'));
                    
                    if (item.local_exists) {
                        // Navigate to subdirectory
                        const newPath = `${path}/${item.name}`;
                        this.updateSymlinkBreadcrumb(newPath, dialog);
                        await this.loadSymlinkDirectoryContents(newPath, dialog);
                    } else {
                        // Can't navigate to non-local directory, but can select it
                        dirItem.classList.add('selected');
                        this.selectedTargetPath = item.path;
                        dialog.querySelector('.fs-symlink-create').disabled = false;
                    }
                });
                
                dirItem.addEventListener('dblclick', () => {
                    if (item.local_exists) {
                        // Select this directory as target
                        contentsDiv.querySelectorAll('.fs-symlink-dir-item').forEach(el => 
                            el.classList.remove('selected'));
                        dirItem.classList.add('selected');
                        this.selectedTargetPath = item.path;
                        dialog.querySelector('.fs-symlink-create').disabled = false;
                    }
                });
                
                contentsDiv.appendChild(dirItem);
            });
            
            // Add "Select Current Directory" option
            const selectCurrentBtn = document.createElement('div');
            selectCurrentBtn.className = 'fs-symlink-select-current';
            selectCurrentBtn.innerHTML = `
                <span class="fs-symlink-dir-icon">📍</span>
                <span class="fs-symlink-dir-name">Select "${path}"</span>
            `;
            
            selectCurrentBtn.addEventListener('click', () => {
                contentsDiv.querySelectorAll('.fs-symlink-dir-item, .fs-symlink-select-current').forEach(el => 
                    el.classList.remove('selected'));
                selectCurrentBtn.classList.add('selected');
                this.selectedTargetPath = path;
                dialog.querySelector('.fs-symlink-create').disabled = false;
            });
            
            contentsDiv.appendChild(selectCurrentBtn);
            
        } catch (error) {
            console.error('Error loading symlink directory contents:', error);
            dialog.querySelector('.fs-symlink-contents').innerHTML = 
                `<div class="fs-error">Error loading directory: ${error.message}</div>`;
        }
    }

    updateSymlinkBreadcrumb(path, dialog) {
        const breadcrumb = dialog.querySelector('.fs-symlink-breadcrumb');
        const parts = path.split('/');
        
        breadcrumb.innerHTML = '';
        
        parts.forEach((part, index) => {
            const pathSoFar = parts.slice(0, index + 1).join('/');
            const span = document.createElement('span');
            span.className = 'fs-breadcrumb-item';
            span.textContent = part;
            span.dataset.path = pathSoFar;
            
            span.addEventListener('click', async () => {
                await this.loadSymlinkDirectoryContents(pathSoFar, dialog);
            });
            
            breadcrumb.appendChild(span);
            
            if (index < parts.length - 1) {
                const separator = document.createElement('span');
                separator.className = 'fs-breadcrumb-separator';
                separator.textContent = ' / ';
                breadcrumb.appendChild(separator);
            }
        });
    }

    async createSymlink(sourceItem, targetPath) {
        if (!this.modal) return;
        
        try {
            UIComponents.showMessage(this.modal, 'Creating symlink...', false);
            
            const response = await fetch('/filesystem/create_symlink', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_path: sourceItem.path,
                    target_path: targetPath
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showMessage(this.modal, result.message, false);
                // Refresh current directory to show new symlink
                await this.refreshCurrentDirectory();
            } else {
                UIComponents.showMessage(this.modal, `Error: ${result.error}`, true);
            }
            
        } catch (error) {
            console.error('Error creating symlink:', error);
            UIComponents.showMessage(this.modal, `Error creating symlink: ${error.message}`, true);
        }
    }

    addSymlinkDialogStyles() {
        if (document.querySelector('#fs-symlink-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'fs-symlink-styles';
        style.textContent = `
            .fs-symlink-dialog-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .fs-symlink-dialog {
                background: var(--comfy-menu-bg);
                border: 2px solid var(--border-color);
                border-radius: 8px;
                min-width: 500px;
                max-width: 700px;
                max-height: 80vh;
                display: flex;
                flex-direction: column;
            }
            
            .fs-symlink-header {
                padding: 16px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .fs-symlink-header h3 {
                margin: 0;
                color: var(--input-text);
                font-size: 18px;
            }
            
            .fs-symlink-close {
                background: none;
                border: none;
                color: var(--input-text);
                font-size: 20px;
                cursor: pointer;
                padding: 4px 8px;
                border-radius: 4px;
            }
            
            .fs-symlink-close:hover {
                background: var(--comfy-input-bg);
            }
            
            .fs-symlink-content {
                padding: 16px;
                flex: 1;
                overflow-y: auto;
            }
            
            .fs-symlink-source {
                margin-bottom: 24px;
            }
            
            .fs-symlink-source label {
                display: block;
                color: var(--input-text);
                font-weight: 600;
                margin-bottom: 8px;
            }
            
            .fs-symlink-source-path {
                font-family: monospace;
                background: var(--comfy-input-bg);
                padding: 8px 12px;
                border-radius: 4px;
                color: var(--input-text);
                font-weight: 600;
                margin-bottom: 4px;
            }
            
            .fs-symlink-source-full {
                font-family: monospace;
                color: var(--descrip-text);
                font-size: 12px;
            }
            
            .fs-symlink-target label {
                display: block;
                color: var(--input-text);
                font-weight: 600;
                margin-bottom: 8px;
            }
            
            .fs-symlink-browser {
                border: 1px solid var(--border-color);
                border-radius: 4px;
                background: var(--comfy-input-bg);
            }
            
            .fs-symlink-breadcrumb {
                padding: 8px 12px;
                border-bottom: 1px solid var(--border-color);
                font-family: monospace;
                font-size: 12px;
            }
            
            .fs-breadcrumb-item {
                color: var(--input-text);
                cursor: pointer;
                padding: 2px 4px;
                border-radius: 2px;
            }
            
            .fs-breadcrumb-item:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .fs-breadcrumb-separator {
                color: var(--descrip-text);
            }
            
            .fs-symlink-contents {
                max-height: 200px;
                overflow-y: auto;
                padding: 8px;
            }
            
            .fs-symlink-dir-item,
            .fs-symlink-select-current {
                display: flex;
                align-items: center;
                padding: 8px 12px;
                margin: 2px 0;
                border-radius: 4px;
                cursor: pointer;
                transition: background-color 0.2s;
            }
            
            .fs-symlink-dir-item:hover,
            .fs-symlink-select-current:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .fs-symlink-dir-item.selected,
            .fs-symlink-select-current.selected {
                background: var(--comfy-menu-bg);
                border: 1px solid var(--border-color);
            }
            
            .fs-symlink-dir-icon {
                margin-right: 8px;
            }
            
            .fs-symlink-dir-name {
                color: var(--input-text);
                font-size: 14px;
            }
            
            .fs-symlink-select-current .fs-symlink-dir-name {
                font-weight: 600;
                color: var(--comfy-menu-bg);
            }
            
            .fs-symlink-actions {
                padding: 16px;
                border-top: 1px solid var(--border-color);
                display: flex;
                gap: 12px;
                justify-content: flex-end;
            }
            
            .fs-symlink-cancel,
            .fs-symlink-create {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
            }
            
            .fs-symlink-cancel {
                background: var(--comfy-input-bg);
                color: var(--input-text);
            }
            
            .fs-symlink-cancel:hover {
                background: var(--comfy-menu-bg);
            }
            
            .fs-symlink-create {
                background: var(--comfy-menu-bg);
                color: var(--input-text);
            }
            
            .fs-symlink-create:hover:not(:disabled) {
                background: var(--comfy-input-bg);
            }
            
            .fs-symlink-create:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            
            .fs-error {
                color: #ff6b6b;
                text-align: center;
                padding: 16px;
                font-style: italic;
            }
        `;
        
        document.head.appendChild(style);
    }

     startGlobalModelsMonitoring() {
        this.stopGlobalModelsMonitoring(); // Clear existing before starting new
        this.globalModelsMonitoringInterval = setInterval(() => {
            this.updateGlobalModelDownloadProgress();
        }, 3000);
    }

    stopGlobalModelsMonitoring() {
        if (this.globalModelsMonitoringInterval) {
            clearInterval(this.globalModelsMonitoringInterval);
            this.globalModelsMonitoringInterval = null;
        }
    }

    startWorkflowMonitoring() {
        this.stopWorkflowMonitoring(); // Clear existing
        let lastWorkflowString = localStorage.getItem("workflow");
        
        this.workflowMonitoringInterval = setInterval(async () => {
            try {
                const currentWorkflowString = localStorage.getItem("workflow");
                if (currentWorkflowString !== lastWorkflowString) {
                    lastWorkflowString = currentWorkflowString;
                    if (currentWorkflowString && this.workflowMonitor.enabled) {
                        await this.analyzeCurrentWorkflow();
                    }
                }
            } catch (error) {
                console.error('Error in workflow monitoring:', error);
            }
        }, 2000);
    }

    stopWorkflowMonitoring() {
        if (this.workflowMonitoringInterval) {
            clearInterval(this.workflowMonitoringInterval);
            this.workflowMonitoringInterval = null;
        }
    }

    async analyzeCurrentWorkflow() {
        try {
            const workflowJSON = localStorage.getItem("workflow");
            if (!workflowJSON) return;
            const workflow = JSON.parse(workflowJSON);
            
            const response = await api.fetchApi('/filesystem/analyze_workflow', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ workflow: workflow })
            });
            const result = await response.json();
            if (result.success) {
                this.workflowMonitor.lastAnalysis = result.analysis;
                if (result.analysis.missing_models > 0) this.showWorkflowAnalysisNotification(result.analysis);
            }
        } catch (error) { console.error('Error analyzing workflow:', error); }
    }

    showWorkflowAnalysisNotification(analysis) {
        const existingNotification = document.querySelector('.fs-workflow-notification');
        if (existingNotification) existingNotification.remove();
        
        const notification = document.createElement('div');
        notification.className = 'fs-workflow-notification';
        const availableCount = analysis.available_for_download || 0;
        const unavailableCount = analysis.unavailable_models || 0;
        
        notification.innerHTML = `
            <div class="fs-notification-content">
                <h4>🔍 Workflow Analysis</h4>
                <p>Found ${analysis.missing_models} missing model(s) out of ${analysis.total_models} total</p>
                ${availableCount > 0 ? `<p class="fs-available-info">📥 ${availableCount} available</p>` : ''}
                ${unavailableCount > 0 ? `<p class="fs-unavailable-info">❌ ${unavailableCount} unavailable</p>` : ''}
                <div class="fs-missing-models-list">
                    ${analysis.missing_list.map(model => {
                        const isAvailable = analysis.global_availability[model];
                        const modelInfo = analysis.available_models && analysis.available_models[model];
                        const sizeInfo = modelInfo && modelInfo.size ? ` (${this.formatFileSize(modelInfo.size)})` : '';
                        return `<div class="fs-missing-model-item ${isAvailable ? 'available' : 'unavailable'}">
                                    <span class="fs-model-name" title="${model}">${model}${sizeInfo}</span>
                                    ${isAvailable ? `<button class="fs-download-model-btn" data-model="${model}">📥</button>` : `<span>❌</span>`}
                                </div>`;
                    }).join('')}
                </div>
                <div class="fs-notification-actions">
                    ${availableCount > 0 ? `<button class="fs-download-all-btn">📥 All (${availableCount})</button>` : ''}
                    <button class="fs-close-notification-btn">×</button>
                </div>
            </div>`;
        
        notification.querySelector('.fs-close-notification-btn').addEventListener('click', () => notification.remove());
        const downloadAllBtn = notification.querySelector('.fs-download-all-btn');
        if (downloadAllBtn) downloadAllBtn.addEventListener('click', () => this.downloadAllMissingModels());
        notification.querySelectorAll('.fs-download-model-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.downloadSingleMissingModel(e.target.dataset.model));
        });
        document.body.appendChild(notification);
        setTimeout(() => { if (notification.parentNode) notification.remove(); }, analysis.missing_models > 5 ? 15000 : 10000);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024, sizes = ['B', 'KB', 'MB', 'GB', 'TB'], i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async downloadAllMissingModels() {
        try {
            const response = await api.fetchApi('/filesystem/auto_download_missing', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            const result = await response.json();
            if (result.success) {
                this.showNotificationMessage(`Started downloading ${Object.keys(result.download_results).length} models`);
                setTimeout(() => this.analyzeCurrentWorkflow(), 3000);
            }
        } catch (error) { this.showNotificationMessage('Error downloading models', true); }
    }

    async downloadSingleMissingModel(modelPath) {
        try {
            const success = await this.downloadGlobalModel(modelPath);
            if (success) {
                this.showNotificationMessage(`Started downloading ${modelPath}`);
                setTimeout(() => this.analyzeCurrentWorkflow(), 3000);
            } else this.showNotificationMessage(`Failed to start download for ${modelPath}`, true);
        } catch (error) { this.showNotificationMessage(`Error downloading ${modelPath}`, true); }
    }

    showNotificationMessage(message, isError = false) {
        // Add styles if they don't exist
        this.addNotificationStyles();
        
        const notification = document.createElement('div');
        notification.className = `fs-notification-message ${isError ? 'fs-error' : 'fs-success'}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        setTimeout(() => { if (notification.parentNode) notification.remove(); }, 3000);
    }

    addNotificationStyles() {
        if (document.querySelector('#fs-notification-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'fs-notification-styles';
        style.textContent = `
            .fs-notification-message {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10001;
                padding: 12px 16px;
                border-radius: 6px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                font-weight: 500;
                max-width: 400px;
                word-wrap: break-word;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
                transform: translateX(100%);
                animation: slideIn 0.3s ease-out forwards;
                opacity: 0;
                animation: fadeInSlide 0.3s ease-out forwards;
            }
            
            .fs-notification-message.fs-success {
                background: #10b981;
                color: white;
                border-left: 4px solid #059669;
            }
            
            .fs-notification-message.fs-error {
                background: #ef4444;
                color: white;
                border-left: 4px solid #dc2626;
            }
            
            @keyframes fadeInSlide {
                0% {
                    opacity: 0;
                    transform: translateX(100%);
                }
                100% {
                    opacity: 1;
                    transform: translateX(0);
                }
            }
            
            .fs-notification-message:hover {
                transform: translateX(0) scale(1.02);
                transition: transform 0.2s ease-out;
            }
        `;
        
        document.head.appendChild(style);
    }

    async getWorkflowMonitorStatus() {
        try {
            const response = await api.fetchApi('/filesystem/workflow_monitor_status');
            const result = await response.json();
            if (result.success) return result.status;
        } catch (error) { console.error('Error getting workflow monitor status:', error); } return null;
    }

    async toggleAutoDownload(enabled) {
        try {
            const response = await api.fetchApi('/filesystem/toggle_auto_download', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: enabled })
            });
            const result = await response.json();
            if (result.success) this.workflowMonitor.enabled = enabled;
        } catch (error) { console.error('Error toggling auto-download:', error); }
    }

    async updateGlobalModelDownloadProgress() {
        try {
            const response = await api.fetchApi('/filesystem/global_model_download_progress');
            const result = await response.json();
            
            if (result.success) {
                this.downloadProgress = result.progress;
                
                // GUARD: Only update UI if the modal is active
                if (this.modal) {
                    Object.entries(result.progress).forEach(([modelPath, progressData]) => {
                        UIComponents.showGlobalModelProgress(this.modal, modelPath, progressData);
                        
                        // Clean up completed or failed downloads from cache after some time
                        if (['downloaded', 'failed', 'cancelled'].includes(progressData.status)) {
                            setTimeout(() => {
                                if (this.downloadProgress[modelPath] && 
                                    this.downloadProgress[modelPath].status === progressData.status) {
                                    // Clear from progress tracking after display
                                    this.clearGlobalModelProgress(modelPath);
                                }
                            }, 3000); // Reduced cleanup time to 3 seconds for faster UI updates
                        }
                    });
                }
            }
        } catch (error) {
            // Silently handle errors to avoid spam
        }
    }

    async clearGlobalModelProgress(modelPath) {
        try {
            const response = await api.fetchApi('/filesystem/clear_global_model_progress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_path: modelPath })
            });
            const result = await response.json();
            
            if (result.success) {
                // Remove from local cache
                if (this.downloadProgress[modelPath]) {
                    delete this.downloadProgress[modelPath];
                }
                console.log(`🧹 Cleared progress for: ${modelPath}`);
            }
        } catch (error) {
            console.error('Error clearing global model progress:', error);
        }
    }

    async handleGlobalModelDownload(item) {
        if (!this.modal) return false; // Guard if modal is not active
        if (item.global_exists && !item.local_exists && item.downloadable) {
            const modelPath = item.global_model_path || item.path;
            
            // Check if there's an active download (but allow retries for cancelled/failed)
            const currentProgress = this.downloadProgress[modelPath];
            if (currentProgress && currentProgress.status === 'downloading') {
                UIComponents.showMessage(this.modal, `Already downloading ${modelPath}`, false);
                return false;
            }
            
            try {
                UIComponents.showMessage(this.modal, `Starting download for ${modelPath}...`, false);
                
                // Show initial progress (this will replace any existing retry button)
                UIComponents.showGlobalModelProgress(this.modal, modelPath, {
                    status: 'downloading', 
                    progress: 0, 
                    downloaded_size: 0, 
                    total_size: item.size || 0,
                    message: '🚀 Initiating download...'
                });
                
                const response = await api.fetchApi('/filesystem/download_global_model', {
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' }, 
                    body: JSON.stringify({ model_path: modelPath })
                });
                const result = await response.json();
                
                if (result.success) {
                    UIComponents.showMessage(this.modal, `Download started for ${modelPath}`, false);
                    return true;
                } else {
                    UIComponents.showMessage(this.modal, `Error: ${result.error || 'Failed to start download'}`, true);
                    // Update progress to show error state with retry option
                    UIComponents.showGlobalModelProgress(this.modal, modelPath, {
                        status: 'failed',
                        progress: 0,
                        message: `❌ ${result.error || 'Failed to start download'} - Click retry to try again`
                    });
                    return false;
                }
            } catch (error) { 
                UIComponents.showMessage(this.modal, `Error: ${error.message}`, true);
                // Update progress to show error state with retry option
                UIComponents.showGlobalModelProgress(this.modal, modelPath, {
                    status: 'failed',
                    progress: 0,
                    message: `❌ ${error.message} - Click retry to try again`
                });
                return false;
            }
        }
        return false;
    }

    async cancelGlobalModelDownload(modelPath) {
        if (!this.modal) return; // Guard
        try {
            const response = await api.fetchApi('/filesystem/cancel_global_model_download', {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ model_path: modelPath })
            });
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showMessage(this.modal, `Cancelled download for ${modelPath}`, false);
                // Don't hide progress immediately - let the backend update show the cancelled state with retry button
            } else { 
                UIComponents.showMessage(this.modal, `Error: ${result.error || 'Failed to cancel'}`, true); 
            }
        } catch (error) { 
            UIComponents.showMessage(this.modal, `Error: ${error.message}`, true); 
        }
    }


    startGlobalModelDownloadProgress(modelPath) { // This seems for a specific model, not the general poller
        if (!this.modal) return; // Guard
        const updateInterval = setInterval(async () => {
            if (!this.modal) { // Also check inside interval in case modal closes during polling
                clearInterval(updateInterval);
                return;
            }
            try {
                const response = await api.fetchApi('/filesystem/global_model_download_progress');
                const result = await response.json();
                
                if (result.success) {
                    this.downloadProgress = result.progress;
                    const progress = result.progress[modelPath];
                    if (progress) {
                        const modelElement = this.modal.querySelector(`.fs-model-item[data-global-model-path="${modelPath}"]`); // Ensure using this.modal
                        if (modelElement) {
                            const progressBar = modelElement.querySelector('.fs-download-progress_bar');
                            if (progressBar) {
                                progressBar.style.width = `${progress.percentage}%`;
                                progressBar.setAttribute('aria-valuenow', progress.percentage);
                                const progressText = modelElement.querySelector('.fs-download-progress_text');
                                if (progressText) progressText.textContent = `${progress.downloaded} / ${progress.total} (${progress.percentage}%)`;
                            }
                        }
                        if (progress.status === 'completed' || progress.status === 'error') clearInterval(updateInterval);
                    } else { // Progress for this specific modelPath might not be available anymore
                        clearInterval(updateInterval); // Stop if no progress data for this model
                    }
                }
            } catch (error) {
                clearInterval(updateInterval);
            }
        }, 3000);
    }

    setupMissingModelsHandler() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        const missingModelsDialog = node.querySelector?.('.comfy-missing-models') || 
                                                  (node.classList?.contains('comfy-missing-models') ? node : null);
                        if (missingModelsDialog) this.initializeMissingModelsDialog(missingModelsDialog); // Pass the dialog itself
                    }
                });
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    initializeMissingModelsDialog(dialogElement) {
        this.addMissingModelsStyles();
        const downloadButtons = dialogElement.querySelectorAll('button[aria-label*="Download"]');
        downloadButtons.forEach((button) => {
            const modelInfo = this.extractModelInfoFromButton(button);
            if (modelInfo) {
                const newButton = button.cloneNode(true);
                button.parentNode.replaceChild(newButton, button);
                newButton.addEventListener('click', (e) => {
                    e.preventDefault(); e.stopPropagation();
                    this.handleMissingModelDownload(modelInfo, newButton);
                });
                this.improveMissingModelLayout(newButton, modelInfo);
                this.addProgressContainer(newButton, modelInfo);
            }
        });
    }

    addMissingModelsStyles() {
        if (document.querySelector('#missing-models-custom-styles')) return;
        console.log('Adding custom styles for missing models dialog');
        const style = document.createElement('style');
        style.id = 'missing-models-custom-styles';
        style.textContent = `/* ... Your CSS from before ... */
            .comfy-missing-models .p-listbox-option { padding: 16px !important; border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important; transition: background-color 0.2s ease !important; }
            .comfy-missing-models .p-listbox-option:hover { background-color: rgba(255, 255, 255, 0.05) !important; }
            .fs-missing-model-container { display: flex; flex-direction: column; gap: 12px; width: 100%; }
            .fs-missing-model-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
            .fs-missing-model-info { flex: 1; min-width: 0; }
            .fs-missing-model-title { font-weight: 600; font-size: 14px; color: var(--input-text); margin-bottom: 4px; word-break: break-word; }
            .fs-missing-model-path { font-size: 12px; color: rgba(255, 255, 255, 0.7); font-family: monospace; }
            .fs-missing-model-actions { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
            .fs-missing-model-progress { margin-top: 8px; padding: 12px; background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; border-left: 3px solid #007bff; }
            .fs-progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
            .fs-progress-text { color: var(--input-text); font-size: 12px; font-weight: 500; }
            .fs-progress-percentage { color: #007bff; font-size: 11px; font-weight: 600; }
            .fs-cancel-download { background: #dc3545; color: white; border: none; border-radius: 4px; width: 20px; height: 20px; font-size: 10px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; transition: all 0.2s ease; }
            .fs-cancel-download:hover { background: #c82333; transform: scale(1.05); }
            .fs-progress-bar-container { width: 100%; height: 6px; background-color: rgba(255, 255, 255, 0.1); border-radius: 3px; overflow: hidden; position: relative; }
            .fs-progress-bar-fill { height: 100%; background: linear-gradient(90deg, #007bff, #0056b3); transition: width 0.3s ease; border-radius: 3px; position: relative; }
            .fs-progress-bar-fill::after { content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.3) 50%, transparent 100%); animation: shimmer 2s infinite; }
            @keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
            .fs-download-complete { text-align: center; padding: 12px; font-weight: 600; color: #28a745; background-color: rgba(40, 167, 69, 0.1); border: 1px solid rgba(40, 167, 69, 0.3); border-radius: 6px; }
            .fs-download-error { text-align: center; padding: 12px; background-color: rgba(220, 53, 69, 0.1); border: 1px solid rgba(220, 53, 69, 0.3); border-radius: 6px; }
            .fs-download-error-text { color: #dc3545; font-size: 12px; margin-bottom: 8px; }
            .fs-retry-download { background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 11px; padding: 6px 12px; transition: all 0.2s ease; font-weight: 500; }
            .fs-retry-download:hover { background: #0056b3; transform: translateY(-1px); }
            .comfy-missing-models button[aria-label*="Download"] { background: linear-gradient(135deg, #007bff, #0056b3) !important; color: white !important; border: none !important; padding: 8px 16px !important; border-radius: 6px !important; font-size: 12px !important; cursor: pointer !important; transition: all 0.2s ease !important; font-weight: 500 !important; box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3) !important; }
            .comfy-missing-models button[aria-label*="Download"]:hover { background: linear-gradient(135deg, #0056b3, #004494) !important; transform: translateY(-1px) !important; box-shadow: 0 4px 8px rgba(0, 123, 255, 0.4) !important; }
            .comfy-missing-models button[aria-label*="Copy URL"] { background: rgba(108, 117, 125, 0.2) !important; color: var(--input-text) !important; border: 1px solid rgba(108, 117, 125, 0.5) !important; padding: 8px 16px !important; border-radius: 6px !important; font-size: 12px !important; cursor: pointer !important; transition: all 0.2s ease !important; font-weight: 500 !important; }
            .comfy-missing-models button[aria-label*="Copy URL"]:hover { background: rgba(108, 117, 125, 0.3) !important; transform: translateY(-1px) !important; }
        `; // Your CSS from before
        document.head.appendChild(style);
    }

    improveMissingModelLayout(button, modelInfo) {
        const listItem = button.closest('li[role="option"]'); if (!listItem) return;
        const existingContent = listItem.querySelector('div[data-v-7a5ec643]'); if (!existingContent) return;
        const container = document.createElement('div'); container.className = 'fs-missing-model-container';
        const header = document.createElement('div'); header.className = 'fs-missing-model-header';
        const infoSection = document.createElement('div'); infoSection.className = 'fs-missing-model-info';
        const titleElement = document.createElement('div'); titleElement.className = 'fs-missing-model-title'; titleElement.textContent = modelInfo.filename;
        const pathElement = document.createElement('div'); pathElement.className = 'fs-missing-model-path'; pathElement.textContent = `${modelInfo.category}/${modelInfo.filename}`;
        infoSection.appendChild(titleElement); infoSection.appendChild(pathElement);
        const actionsSection = document.createElement('div'); actionsSection.className = 'fs-missing-model-actions';
        const downloadBtn = existingContent.querySelector('button[aria-label*="Download"]');
        const copyBtn = existingContent.querySelector('button[aria-label*="Copy URL"]');
        if (downloadBtn) actionsSection.appendChild(downloadBtn); if (copyBtn) actionsSection.appendChild(copyBtn);
        header.appendChild(infoSection); header.appendChild(actionsSection); container.appendChild(header);
        existingContent.replaceWith(container);
    }

    addProgressContainer(button, modelInfo) {
        const container = button.closest('.fs-missing-model-container'); if (!container) return;
        const progressContainer = document.createElement('div'); progressContainer.className = 'fs-missing-model-progress'; progressContainer.style.display = 'none';
        progressContainer.innerHTML = `
            <div class="fs-progress-header"> <span class="fs-progress-text">Preparing...</span> <div style="display:flex;align-items:center;gap:8px;"> <span class="fs-progress-percentage">0%</span> <button class="fs-cancel-download" title="Cancel">×</button> </div> </div>
            <div class="fs-progress-bar-container"> <div class="fs-progress-bar-fill" style="width:0%"></div> </div>`;
        container.appendChild(progressContainer);
        const cancelBtn = progressContainer.querySelector('.fs-cancel-download');
        cancelBtn.addEventListener('click', () => this.cancelMissingModelDownload(modelInfo));
    }

    async handleMissingModelDownload(modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        button.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'block';
        const sessionId = `missing_model_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        try {
            this.startMissingModelProgressPolling(sessionId, modelInfo, button);
            const response = await api.fetchApi('/filesystem/upload_from_direct_url', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ direct_url: modelInfo.url, path: `models/${modelInfo.category}`, filename: modelInfo.filename, overwrite: true, session_id: sessionId })
            });
            if (!response.ok) { const e = await response.json(); throw new Error(e.error || `HTTP ${response.status}`); }
        } catch (error) { this.showModelDownloadError(modelInfo, button, error.message); }
    }

    startMissingModelProgressPolling(sessionId, modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        const progressText = progressContainer?.querySelector('.fs-progress-text');
        const progressFill = progressContainer?.querySelector('.fs-progress-bar-fill');
        const progressPercentage = progressContainer?.querySelector('.fs-progress-percentage');
        if (progressContainer) progressContainer.style.display = 'block';

        const pollInterval = setInterval(async () => {
            try {
                const response = await api.fetchApi(`/filesystem/direct_link_progress/${sessionId}`);
                const progress = await response.json();
                if (progressText) progressText.textContent = progress.message || 'Downloading...';
                if (progressFill) progressFill.style.width = `${progress.percentage || 0}%`;
                if (progressPercentage) progressPercentage.textContent = `${Math.round(progress.percentage || 0)}%`;
                if (progress.status === 'completed') { clearInterval(pollInterval); this.showModelDownloadComplete(modelInfo, button); }
                else if (progress.status === 'error') { clearInterval(pollInterval); this.showModelDownloadError(modelInfo, button, progress.message); }
                else if (progress.status === 'cancelled') { clearInterval(pollInterval); this.resetModelDownloadUI(modelInfo, button); }
            } catch (error) { clearInterval(pollInterval); this.showModelDownloadError(modelInfo, button, 'Poll error'); }
        }, 500);
        modelInfo.pollInterval = pollInterval; modelInfo.sessionId = sessionId;
    }

    showModelDownloadComplete(modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.innerHTML = `<div class="fs-download-complete"><span>✅ Complete</span><div style="font-size:11px;margin-top:4px;opacity:0.8;">${modelInfo.filename} ready</div></div>`;
            progressContainer.style.display = 'block';
        }
        button.style.display = 'none';
    }

    showModelDownloadError(modelInfo, button, errorMessage) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.innerHTML = `<div class="fs-download-error"><div class="fs-download-error-text">❌ ${errorMessage}</div><button class="fs-retry-download">🔄 Retry</button></div>`;
            progressContainer.style.display = 'block';
            const retryBtn = progressContainer.querySelector('.fs-retry-download');
            if (retryBtn) retryBtn.addEventListener('click', () => { this.resetModelDownloadUI(modelInfo, button); this.handleMissingModelDownload(modelInfo, button); });
        }
    }

    resetModelDownloadUI(modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.style.display = 'none';
            progressContainer.innerHTML = `
                <div class="fs-progress-header"> <span class="fs-progress-text">Preparing...</span> <div style="display:flex;align-items:center;gap:8px;"> <span class="fs-progress-percentage">0%</span> <button class="fs-cancel-download" title="Cancel">×</button> </div> </div>
                <div class="fs-progress-bar-container"> <div class="fs-progress-bar-fill" style="width:0%"></div> </div>`;
            const cancelBtn = progressContainer.querySelector('.fs-cancel-download');
            cancelBtn.addEventListener('click', () => this.cancelMissingModelDownload(modelInfo));
        }
        button.style.display = 'inline-block';
        if (modelInfo.pollInterval) { clearInterval(modelInfo.pollInterval); delete modelInfo.pollInterval; }
        delete modelInfo.sessionId;
    }

    extractModelInfoFromButton(button) {
        try {
            const url = button.title || button.getAttribute('title'); if (!url) return null;
            const listItem = button.closest('li[role="option"]'); if (!listItem) return null;
            const modelSpan = listItem.querySelector('span[title]'); if (!modelSpan) return null;
            const modelPath = modelSpan.textContent.trim();
            const pathParts = modelPath.split(' / '); if (pathParts.length !== 2) return null;
            const [category, filename] = pathParts;
            const extParts = filename.split('.'); const extension = extParts.pop();
            const nameWithoutExt = extParts.join('.');
            const sizeMatch = button.textContent.match(/\(([^)]+)\)/); const size = sizeMatch ? sizeMatch[1] : 'Unknown';
            return { url:url.trim(), category:category.trim(), filename:filename.trim(), nameWithoutExt, extension, size, fullPath:`models/${category.trim()}/${filename.trim()}` };
        } catch (error) { console.error('Error extracting model info:', error); return null; }
    }

    async cancelMissingModelDownload(modelInfo) {
        try {
            if (modelInfo.sessionId) {
                const response = await api.fetchApi('/filesystem/cancel_download', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: modelInfo.sessionId, download_type: 'direct-link' })
                });
                const result = await response.json();
                if (!result.success) console.error('Failed to cancel model download:', result.error);
            }
            if (modelInfo.pollInterval) { clearInterval(modelInfo.pollInterval); delete modelInfo.pollInterval; }
            const containers = document.querySelectorAll('.fs-missing-model-container');
            for (const container of containers) {
                const titleElement = container.querySelector('.fs-missing-model-title');
                if (titleElement && titleElement.textContent === modelInfo.filename) {
                    const button = container.querySelector('button[aria-label*="Download"]');
                    if (button) { this.resetModelDownloadUI(modelInfo, button); break; }
                }
            }
        } catch (error) { console.error('Error cancelling model download:', error); }
    }
}