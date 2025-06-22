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
        this.isRenamingItem = false; // Add state for renaming
        this.uploadProgressInterval = null;
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
        this.activeContextMenu = { itemPath: null, element: null }; // For context menu
        this.boundHandleDocumentClick = this.handleDocumentClick.bind(this); // For closing context menu
        this.globalModelsStructure = null;
        this.downloadProgress = {};
        this.workflowMonitor = {
            enabled: true,
            autoDownload: true,
            lastAnalysis: null
        };
        this.missingModelsHandler = null;
        this.setupMissingModelsHandler();
        this.startGlobalModelsMonitoring();
        this.startWorkflowMonitoring();

        this.progressPollingInterval = null;
        this.activeDownloads = new Set();
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
        modal.querySelector('#fs-rename').addEventListener('click', () => this.showRenameForm()); // Add listener for rename
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

         modal.addEventListener('globalModelCancel', (e) => {
            this.cancelGlobalModelDownload(e.detail.modelPath);
        });
        
        modal.addEventListener('globalModelDownloaded', (e) => {
            this.refreshCurrentDirectory();
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
                this.currentUploadType = type; // Ensure currentUploadType is set
                let destinationPathText = this.currentPath || "FSM Root"; // Default to current browsed path

                if (this.selectedItems.size === 1) {
                    const selectedPath = Array.from(this.selectedItems)[0];
                    const selectedItem = this.currentContents.find(item => item.path === selectedPath);
                    if (selectedItem && selectedItem.type === 'directory') {
                        destinationPathText = selectedItem.path; // Target the selected directory
                    }
                }
                // Store this for startUpload
                this.currentUploadDestinationPath = destinationPathText === "FSM Root" ? "" : destinationPathText;


                UIComponents.showUploadForm(modal, type, destinationPathText);
                this.setUploadButtonState(true); // Enable button when form is shown
                this.attachUploadFormInputListeners(modal);
            });
        });
        
        // Back button
        modal.querySelector('#fs-upload-back').addEventListener('click', () => {
            UIComponents.showUploadOptions(modal);
            // No need to change button state here, as options view doesn't have it
        });
        
        // Upload actions
        modal.querySelector('#fs-upload-start').addEventListener('click', () => this.startUpload());
        modal.querySelector('#fs-upload-cancel').addEventListener('click', () => this.closeUploadModal());
        
        // Listen for cancel events from progress bar
        modal.addEventListener('uploadCancel', () => this.cancelUpload());
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeUploadModal();
            }
        });
    }

    attachUploadFormInputListeners(modal) {
        if (!modal) return;
        const formContent = modal.querySelector('.fs-upload-form-content');
        if (!formContent) return;

        const inputs = formContent.querySelectorAll('input[type="text"], input[type="password"], input[type="checkbox"]');
        
        // Remove existing listeners to prevent duplicates if this is called multiple times
        inputs.forEach(input => {
            input.removeEventListener('input', this.boundHandleUploadFormInputChange);
            input.removeEventListener('change', this.boundHandleUploadFormInputChange); // For checkboxes
            // Clear specific listeners if they were attached
            input.removeEventListener('blur', this.boundHandleGdriveFieldValidation);
        });

        // Bind the handler once
        this.boundHandleUploadFormInputChange = this.boundHandleUploadFormInputChange || this.handleUploadFormInputChange.bind(this);
        this.boundHandleGdriveFieldValidation = this.boundHandleGdriveFieldValidation || this.handleGdriveFieldValidation.bind(this);

        inputs.forEach(input => {
            if (input.type === 'checkbox') {
                input.addEventListener('change', this.boundHandleUploadFormInputChange);
            } else {
                input.addEventListener('input', this.boundHandleUploadFormInputChange);
            }

            // Add specific validation for Google Drive filename and extension fields
            if (this.currentUploadType === 'google-drive' && (input.id === 'fs-gdrive-filename' || input.id === 'fs-gdrive-extension')) {
                input.addEventListener('blur', this.boundHandleGdriveFieldValidation);
                // Also remove error on input if it becomes non-empty
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
            this.closeModal();
        }
        
        this.modal = this.createModal();
        document.body.appendChild(this.modal);
        
        // Load root directory
        await this.navigateToPath('');
        // Ensure bound handler is initialized for later use if needed
        this.boundHandleUploadFormInputChange = this.handleUploadFormInputChange.bind(this);
    }

    closeModal() {
        if (this.modal) {
            document.body.removeChild(this.modal);
            this.modal = null;
        }
        this.closeActiveContextMenu(); // Close context menu if open
        // Ensure upload modal and its polling are also closed
        if (this.uploadModal) {
            this.closeUploadModal();
        }
        this.currentPath = '';
        this.selectedItems = new Set();
        this.currentContents = [];
        this.isCreatingFolder = false;
        this.isRenamingItem = false; // Reset renaming state
        this.uploadProgressInterval = null;
        this.currentUploadSessionId = null;
        this.currentUploadType = null;
        this.activeContextMenu = { itemPath: null, element: null };
    }

    updateBreadcrumb() {
        if (!this.modal) return;
        UIComponents.updateBreadcrumb(this.modal, this.currentPath, (path) => this.navigateToPath(path));
    }

    async navigateToPath(path) {
        try {
            this.closeActiveContextMenu(); // Close context menu on navigation
            console.log('Navigating to path:', path);
            // If navigating, clear selection unless it's a refresh of the current path
            if (this.currentPath !== path) {
                this.selectedItems.clear();
            }
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
            (path) => this.navigateToPath(path), // Navigation callback
            (item, triggerElement) => this.showItemContextMenu(item, triggerElement),
            (item) => this.handleGlobalModelDownload(item)
        );
        
        this.updateItemCount();
        
        // Ensure navigation links are properly attached after rendering
        this.attachNavigationHandlers();
    }

    attachNavigationHandlers() {
        if (!this.modal) return;
        
        // Find all directory name links and ensure they have proper click handlers
        const directoryLinks = this.modal.querySelectorAll('.fs-item-name-link[data-type="directory"]');
        directoryLinks.forEach(link => {
            // Remove any existing listeners
            link.removeEventListener('click', this.handleDirectoryLinkClick);
            
            // Add the navigation click handler
            link.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const path = link.dataset.path;
                if (path) {
                    console.log('Navigating to directory:', path);
                    this.navigateToPath(path);
                }
            });
        });
    }

    handleItemClick(item, e) {
        this.closeActiveContextMenu();
        const itemPath = item.path;
        const isNameLinkClicked = e.target.closest('.fs-item-name-link');

        // If it's a directory link click, handle navigation
        if (isNameLinkClicked && item.type === 'directory') {
            e.preventDefault();
            e.stopPropagation();
            console.log('Directory link clicked, navigating to:', itemPath);
            this.navigateToPath(itemPath);
            return;
        }

        // Handle selection
        if (e.ctrlKey || e.metaKey) {
            this.toggleSelection(itemPath);
        } else {
            this.selectItem(itemPath);
        }
    }

    handleItemDoubleClick(item) {
        // This method is no longer the primary way to navigate directories.
        // Kept for potential future use or if other items become double-clickable.
        // Navigation for directories is handled by clicking their name link.
        if (item.type === 'directory') {
            // this.navigateToPath(item.path); // Redundant if name link handles it
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
            this.activeContextMenu.element.remove();
            this.activeContextMenu = { itemPath: null, element: null };
            document.removeEventListener('click', this.boundHandleDocumentClick, true);
        }
    }

    handleDocumentClick(event) {
        if (this.activeContextMenu.element && !this.activeContextMenu.element.contains(event.target)) {
            // Check if the click was on an action trigger for the current context menu's item
            const trigger = event.target.closest('.fs-item-actions-trigger');
            if (trigger) {
                const row = trigger.closest('tr');
                if (row && row.dataset.path === this.activeContextMenu.itemPath) {
                    // Clicked the trigger for the currently open menu, let showItemContextMenu handle it (it will close and reopen)
                    return;
                }
            }
            this.closeActiveContextMenu();
        }
    }

    showItemContextMenu(item, triggerElement) {
        this.closeActiveContextMenu(); // Close any existing menu first

        this.activeContextMenu.itemPath = item.path; // Store path to prevent self-reopen issues

        const actions = [];
        actions.push({ id: 'rename', label: 'Rename', icon: '✏️' });
        if (item.type === 'file') {
            actions.push({ id: 'download', label: 'Download', icon: '⬇️' });
        }
        actions.push({ id: 'delete', label: 'Delete', icon: '🗑️' });
        // Future actions: 'Copy Path', 'Move', etc.

        const menu = UIComponents.createItemContextMenu(actions, (actionId) => {
            this.handleContextMenuAction(actionId, item);
        });
        
        this.activeContextMenu.element = menu;

        // Position menu
        const modalContentRect = this.modal.querySelector('.fs-modal-content').getBoundingClientRect();
        const triggerRect = triggerElement.getBoundingClientRect();
        
        document.body.appendChild(menu); // Append to body to avoid overflow issues from modal

        menu.style.top = `${triggerRect.bottom}px`;
        menu.style.left = `${triggerRect.left}px`;

        // Adjust if menu goes off-screen
        const menuRect = menu.getBoundingClientRect();
        if (menuRect.right > window.innerWidth - 10) {
            menu.style.left = `${triggerRect.right - menuRect.width}px`;
        }
        if (menuRect.bottom > window.innerHeight - 10) {
            menu.style.top = `${triggerRect.top - menuRect.height}px`;
        }
        
        // Add listener to close on outside click
        // Use capture phase to ensure it runs before other click listeners that might stop propagation
        setTimeout(() => { // Timeout to prevent immediate closing due to the click that opened it
            document.addEventListener('click', this.boundHandleDocumentClick, true);
        }, 0);
    }

    async handleContextMenuAction(actionId, item) {
        this.closeActiveContextMenu(); // Close menu after action selected
        
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
            default:
                console.warn('Unknown context menu action:', actionId);
        }
    }
    
    showRenameFormForItem(item) {
        this.selectedItems.clear();
        this.selectedItems.add(item.path);
        this.updateSelection(); // Visually update selection
        this.updateActions();   // Update header buttons based on new selection
        this.showRenameForm();  // Now show the form
    }

    async deleteSingleItem(item) {
        UIComponents.showMessage(this.modal, ''); // Clear previous messages
        const confirmMessage = `Are you sure you want to delete "${item.name}"? This action cannot be undone.`;
        
        const result = await Dialog.show({
            title: "Confirm Delete",
            message: confirmMessage,
            buttons: ["Cancel", "Delete"],
            defaultButton: 0,
            type: 'danger'
        });
        
        if (result !== 1) return; // User cancelled

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
            await this.refreshCurrentDirectory(); // Refresh even on error
        }
    }


    updateActions() {
        if (!this.modal) return;
        // General state for Delete and Download (bulk)
        UIComponents.updateActions(this.modal, this.selectedItems.size > 0); 
        
        const renameBtn = this.modal.querySelector('#fs-rename');
        const uploadBtn = this.modal.querySelector('#fs-upload');
        const createFolderBtn = this.modal.querySelector('#fs-create-folder');
        const downloadSelectedBtn = this.modal.querySelector('#fs-download-selected');

        // Header Rename button: enabled if exactly one item is selected
        if (renameBtn) {
            renameBtn.disabled = this.selectedItems.size !== 1;
        }

        // Header Download Selected button: enabled if items are selected and at least one is a file
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
            canUpload = true; // Upload to currentPath
            canCreateFolder = true; // Create in currentPath
        } else if (this.selectedItems.size === 1) {
            const selectedPath = Array.from(this.selectedItems)[0];
            const selectedItem = this.currentContents.find(item => item.path === selectedPath);
            if (selectedItem && selectedItem.type === 'directory') {
                canUpload = true; // Upload to selected folder
                canCreateFolder = true; // Create in selected folder
            }
        }
        // If selectedItems.size > 1, both remain false (disabled)

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
        this.hideCreateFolderForm(); // Hide create folder form if open

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

        UIComponents.showMessage(this.modal, ''); // Clear previous messages
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
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    old_path: oldPath,
                    new_name: newName
                })
            });

            const result = await response.json();

            if (result.success) {
                UIComponents.showMessage(this.modal, result.message, false);
                this.hideRenameForm();
                // Update selection to the new path if needed, or just clear and refresh
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
        
        UIComponents.showMessage(this.modal, ''); // Clear previous messages
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
                targetPath = selectedItem.path; // Target the selected directory
            }
        }
        
        try {
            const response = await api.fetchApi('/filesystem/create_directory', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    path: targetPath, // Use determined targetPath
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

        const uploadData = {
            url: url, 
            path: backendDestinationPath, 
        };
        
        let apiEndpoint = '/filesystem/upload';

        if (this.currentUploadType === 'google-drive') {
            apiEndpoint = '/filesystem/upload_from_google_drive';
            const filenameInput = this.uploadModal.querySelector('#fs-gdrive-filename');
            const extensionInput = this.uploadModal.querySelector('#fs-gdrive-extension');
            
            const filename = filenameInput.value.trim();
            let extension = extensionInput.value.trim();

            filenameInput.classList.remove('fs-input-error');
            extensionInput.classList.remove('fs-input-error');

            if (!filename) {
                errors.push('Filename is required for Google Drive.');
                filenameInput.classList.add('fs-input-error');
                hasError = true;
            }
            if (!extension) {
                errors.push('Extension is required for Google Drive.');
                extensionInput.classList.add('fs-input-error');
                hasError = true;
            } else {
                extension = extension.replace(/^\./, ''); // Remove leading dot
                if (!extension) { // If it was just a dot or became empty
                    errors.push('Extension cannot be empty or just a dot.');
                    extensionInput.classList.add('fs-input-error');
                    hasError = true;
                }
            }
            
            if (hasError) {
                UIComponents.showUploadMessage(this.uploadModal, errors.join(' '), true);
                // UIComponents.hideUploadProgress(this.uploadModal);
                return;
            }

            uploadData.filename = filename;
            uploadData.extension = extension;
            uploadData.google_drive_url = url; 
            delete uploadData.url; 
            uploadData.overwrite = this.uploadModal.querySelector('#fs-gdrive-overwrite').checked;
            uploadData.auto_extract_zip = this.uploadModal.querySelector('#fs-gdrive-auto-extract').checked;
        } else if (this.currentUploadType === 'huggingface') {
            apiEndpoint = '/filesystem/download_from_huggingface'; // Correct endpoint
            uploadData.hf_url = url; // Specific key for HF
            delete uploadData.url; // Remove generic url key

            uploadData.overwrite = this.uploadModal.querySelector('#fs-hf-overwrite').checked;
            
            // Check if user provided HF token
            const tokenInput = this.uploadModal.querySelector('#fs-hf-token');
            if (tokenInput && tokenInput.value.trim()) {
                uploadData.user_token = tokenInput.value.trim();
            }
        } else if (this.currentUploadType === 'civitai') {
            apiEndpoint = '/filesystem/download_from_civitai';
            uploadData.civitai_url = url;
            delete uploadData.url;

            uploadData.overwrite = this.uploadModal.querySelector('#fs-civitai-overwrite').checked;
            
            // Check if user provided CivitAI token
            const tokenInput = this.uploadModal.querySelector('#fs-civitai-token');
            if (tokenInput && tokenInput.value.trim()) {
                uploadData.user_token = tokenInput.value.trim();
            }

            // Check if user provided custom filename
            const filenameInput = this.uploadModal.querySelector('#fs-civitai-filename');
            if (filenameInput && filenameInput.value.trim()) {
                uploadData.filename = filenameInput.value.trim();
            }
        } else if (this.currentUploadType === 'direct-link') {
            apiEndpoint = '/filesystem/upload_from_direct_url';
            uploadData.direct_url = url;
            delete uploadData.url;

            uploadData.overwrite = this.uploadModal.querySelector('#fs-direct-overwrite').checked;
            
            // Check if user provided custom filename
            const filenameInput = this.uploadModal.querySelector('#fs-direct-filename');
            if (filenameInput && filenameInput.value.trim()) {
                uploadData.filename = filenameInput.value.trim();
            }
        } else {
            // Handle other types
            if (hasError) { // For non-GDrive, only URL is validated above
                UIComponents.showUploadMessage(this.uploadModal, errors.join(' '), true);
                return;
            }
            // For other types, you might have a generic filename input
            const commonFilenameInput = this.uploadModal.querySelector('#fs-upload-filename');
            if (commonFilenameInput) {
                 uploadData.filename = commonFilenameInput.value.trim();
            }
        }
        
        // If path is effectively FSM root (empty string), prevent upload.
        if (uploadData.path === "") {
            UIComponents.showUploadMessage(this.uploadModal, "Cannot upload to the root. Please select a sub-directory (e.g., models, users) or a folder within them.", true);
            this.setUploadButtonState(true); // Re-enable if validation fails early
            return;
        }

        UIComponents.showUploadProgress(this.uploadModal, 'Starting...', 0);
        const sessionId = 'upload_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this.currentUploadSessionId = sessionId;
        uploadData.session_id = sessionId;
        
        try {
            this.startUploadProgressPolling(sessionId, this.currentUploadType);

            const response = await api.fetchApi(apiEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(uploadData)
            });
            
            // Handle immediate response for access-restricted cases
            if (!response.ok) {
                const errorResult = await response.json();
                this.stopUploadProgressPolling();
                
                if (errorResult.error_type === 'access_restricted') {
                    UIComponents.showUploadMessage(this.uploadModal, errorResult.error, true, true);
                    if (this.currentUploadType === 'civitai') {
                        UIComponents.showCivitAITokenInput(this.uploadModal, true);
                    } else {
                        UIComponents.showHFTokenInput(this.uploadModal, true);
                    }
                } else {
                    UIComponents.showUploadMessage(this.uploadModal, errorResult.error || `Request failed: ${response.statusText}`, true);
                }
                
                UIComponents.hideUploadProgress(this.uploadModal);
                this.setUploadButtonState(true); // Re-enable on failure
                return;
            }

            // For CivitAI, Google Drive, Hugging Face, and Direct Link, let the poller handle the rest
            if (this.currentUploadType === 'civitai' || this.currentUploadType === 'google-drive' || this.currentUploadType === 'huggingface' || this.currentUploadType === 'direct-link') {
                // Progress polling will handle the response
            } else {
                const result = await response.json();
                this.stopUploadProgressPolling();
                if (result.success) {
                    UIComponents.showUploadMessage(this.uploadModal, result.message || 'Upload started successfully.', false);
                    await this.refreshCurrentDirectory();
                } else {
                    if (result.error_type === 'access_restricted') {
                        UIComponents.showUploadMessage(this.uploadModal, result.error, true, true);
                        UIComponents.showCivitAITokenInput(this.uploadModal, true);
                    } else {
                        UIComponents.showUploadMessage(this.uploadModal, result.error || 'Upload failed.', true);
                    }
                    this.setUploadButtonState(true); // Re-enable on failure
                }
                UIComponents.hideUploadProgress(this.uploadModal); 
            }

        } catch (error) {
            this.stopUploadProgressPolling();
            UIComponents.showUploadMessage(this.uploadModal, `Error starting upload: ${error.message}`, true);
            UIComponents.hideUploadProgress(this.uploadModal);
            this.setUploadButtonState(true); // Re-enable on catch
        }
    }

    async cancelUpload() {
        if (!this.currentUploadSessionId) return;
        
        try {
            UIComponents.showUploadMessage(this.uploadModal, 'Cancelling download...', false);
            
            // Send cancellation request to the server
            const response = await api.fetchApi('/filesystem/cancel_download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.currentUploadSessionId,
                    download_type: this.currentUploadType
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showUploadMessage(this.uploadModal, 'Download cancelled successfully', false);
            } else {
                UIComponents.showUploadMessage(this.uploadModal, `Failed to cancel: ${result.error}`, true);
            }
            
        } catch (error) {
            UIComponents.showUploadMessage(this.uploadModal, `Error cancelling download: ${error.message}`, true);
        }
        
        // Stop progress polling and reset state
        this.stopUploadProgressPolling();
        UIComponents.hideUploadProgress(this.uploadModal);
        this.setUploadButtonState(true);
    }

    startUploadProgressPolling(sessionId, uploadType) {
        if (this.uploadProgressInterval) {
            clearInterval(this.uploadProgressInterval);
        }

        let progressApiEndpoint = null;
        if (uploadType === 'google-drive') {
            progressApiEndpoint = `/filesystem/google_drive_progress/${this.currentUploadSessionId}`;
        } else if (uploadType === 'huggingface') {
            progressApiEndpoint = `/filesystem/huggingface_progress/${this.currentUploadSessionId}`;
        } else if (uploadType === 'civitai') {
            progressApiEndpoint = `/filesystem/civitai_progress/${this.currentUploadSessionId}`;
        } else if (uploadType === 'direct-link') {
            progressApiEndpoint = `/filesystem/direct_upload_progress/${this.currentUploadSessionId}`;
        } else {
            return; // No polling for other types
        }

        this.uploadProgressInterval = setInterval(async () => {
            if (!this.uploadModal || !this.currentUploadSessionId) {
                this.stopUploadProgressPolling();
                return;
            }
            try {
                const progressResponse = await api.fetchApi(progressApiEndpoint);
                const progress = await progressResponse.json();

                UIComponents.showUploadProgress(this.uploadModal, progress.message, progress.percentage);

                if (progress.status === 'completed' || progress.status === 'error' || progress.status === 'access_restricted' || progress.status === 'cancelled') {
                    this.stopUploadProgressPolling();
                    
                    if (progress.status === 'completed') {
                        UIComponents.showUploadMessage(this.uploadModal, `✅ ${progress.message}`, false);
                        this.setUploadButtonState(false); // Disable button on successful completion
                        await this.refreshCurrentDirectory();
                    } else if (progress.status === 'cancelled') {
                        UIComponents.showUploadMessage(this.uploadModal, `🚫 ${progress.message}`, false);
                        this.setUploadButtonState(true); // Re-enable button after cancellation
                    } else if (progress.status === 'access_restricted') {
                        // Show access restricted message with HTML support and show token input
                        UIComponents.showUploadMessage(this.uploadModal, progress.message, true, true);
                        if (uploadType === 'civitai') {
                            UIComponents.showCivitAITokenInput(this.uploadModal, true);
                        } else {
                            UIComponents.showHFTokenInput(this.uploadModal, true);
                        }
                        this.setUploadButtonState(true); // Re-enable button for retry with token
                    } else { // error
                        UIComponents.showUploadMessage(this.uploadModal, `❌ ${progress.message || 'An error occurred.'}`, true);
                        this.setUploadButtonState(true); // Re-enable on error
                    }
                }
            } catch (err) {
                console.error('Error polling upload progress:', err);
                UIComponents.showUploadMessage(this.uploadModal, 'Error checking progress.', true);
                this.setUploadButtonState(true); // Re-enable on polling error
                this.stopUploadProgressPolling(); // Stop if polling fails
            }
        }, 500); // Poll every 500ms (increased frequency for better real-time updates)
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

    startGlobalModelsMonitoring() {
        // Monitor download progress for global models
        setInterval(() => {
            this.updateGlobalModelDownloadProgress();
        }, 1000); // Update every second
    }

    startWorkflowMonitoring() {
        // Monitor workflow changes in localStorage
        let lastWorkflowString = localStorage.getItem("workflow");
        
        setInterval(async () => {
            try {
                const currentWorkflowString = localStorage.getItem("workflow");
                
                // Check if workflow changed
                if (currentWorkflowString !== lastWorkflowString) {
                    lastWorkflowString = currentWorkflowString;
                    
                    if (currentWorkflowString && this.workflowMonitor.enabled) {
                        await this.analyzeCurrentWorkflow();
                    }
                }
            } catch (error) {
                console.error('Error in workflow monitoring:', error);
            }
        }, 2000); // Check every 2 seconds
    }

    async analyzeCurrentWorkflow() {
        try {
            const workflowJSON = localStorage.getItem("workflow");
            if (!workflowJSON) return;
            
            const workflow = JSON.parse(workflowJSON);
            
            const response = await api.fetchApi('/filesystem/analyze_workflow', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workflow: workflow })
            });
            
            const result = await response.json();
            if (result.success) {
                this.workflowMonitor.lastAnalysis = result.analysis;
                
                // Show notification if there are missing models
                if (result.analysis.missing_models > 0) {
                    this.showWorkflowAnalysisNotification(result.analysis);
                }
                
                console.log('Workflow analysis:', result.analysis);
            }
        } catch (error) {
            console.error('Error analyzing workflow:', error);
        }
    }

    showWorkflowAnalysisNotification(analysis) {
        // Remove existing notification
        const existingNotification = document.querySelector('.fs-workflow-notification');
        if (existingNotification) {
            existingNotification.remove();
        }
        
        // Create notification with more detailed info
        const notification = document.createElement('div');
        notification.className = 'fs-workflow-notification';
        
        const availableCount = analysis.available_for_download || 0;
        const unavailableCount = analysis.unavailable_models || 0;
        
        notification.innerHTML = `
            <div class="fs-notification-content">
                <h4>🔍 Workflow Analysis</h4>
                <p>Found ${analysis.missing_models} missing model(s) out of ${analysis.total_models} total</p>
                ${availableCount > 0 ? `<p class="fs-available-info">📥 ${availableCount} available for download</p>` : ''}
                ${unavailableCount > 0 ? `<p class="fs-unavailable-info">❌ ${unavailableCount} not available globally</p>` : ''}
                
                <div class="fs-missing-models-list">
                    ${analysis.missing_list.map(model => {
                        const isAvailable = analysis.global_availability[model];
                        const modelInfo = analysis.available_models && analysis.available_models[model];
                        const sizeInfo = modelInfo && modelInfo.size ? ` (${this.formatFileSize(modelInfo.size)})` : '';
                        
                        return `
                            <div class="fs-missing-model-item ${isAvailable ? 'available' : 'unavailable'}">
                                <span class="fs-model-name" title="${model}">${model}${sizeInfo}</span>
                                ${isAvailable ? 
                                    `<button class="fs-download-model-btn" data-model="${model}">📥 Download</button>` :
                                    `<span class="fs-not-available">❌ Not Available</span>`
                                }
                            </div>
                        `;
                    }).join('')}
                </div>
                
                <div class="fs-notification-actions">
                    ${availableCount > 0 ?
                        `<button class="fs-download-all-btn">📥 Download All Available (${availableCount})</button>` : ''
                    }
                    <button class="fs-close-notification-btn">×</button>
                </div>
            </div>
        `;
        
        // Add event listeners
        notification.querySelector('.fs-close-notification-btn').addEventListener('click', () => {
            notification.remove();
        });
        
        const downloadAllBtn = notification.querySelector('.fs-download-all-btn');
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener('click', () => {
                this.downloadAllMissingModels();
            });
        }
        
        notification.querySelectorAll('.fs-download-model-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modelPath = e.target.dataset.model;
                this.downloadSingleMissingModel(modelPath);
            });
        });
        
        document.body.appendChild(notification);
        
        // Auto-hide after 15 seconds if there are many models
        const autoHideDelay = analysis.missing_models > 5 ? 15000 : 10000;
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, autoHideDelay);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async downloadAllMissingModels() {
        try {
            const response = await api.fetchApi('/filesystem/auto_download_missing', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            if (result.success) {
                console.log('Auto-download results:', result.download_results);
                
                // Show success message
                this.showNotificationMessage(
                    `Started downloading ${Object.keys(result.download_results).length} models`
                );
                
                // Re-analyze workflow after a delay
                setTimeout(() => {
                    this.analyzeCurrentWorkflow();
                }, 3000);
            }
        } catch (error) {
            console.error('Error downloading missing models:', error);
            this.showNotificationMessage('Error downloading models', true);
        }
    }

    async downloadSingleMissingModel(modelPath) {
        try {
            const success = await this.downloadGlobalModel(modelPath);
            
            if (success) {
                this.showNotificationMessage(`Started downloading ${modelPath}`);
                
                // Re-analyze workflow after a delay
                setTimeout(() => {
                    this.analyzeCurrentWorkflow();
                }, 3000);
            } else {
                this.showNotificationMessage(`Failed to start download for ${modelPath}`, true);
            }
        } catch (error) {
            console.error('Error downloading single model:', error);
            this.showNotificationMessage(`Error downloading ${modelPath}`, true);
        }
    }

    showNotificationMessage(message, isError = false) {
        const notification = document.createElement('div');
        notification.className = `fs-notification-message ${isError ? 'fs-error' : 'fs-success'}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 3000);
    }

    async getWorkflowMonitorStatus() {
        try {
            const response = await api.fetchApi('/filesystem/workflow_monitor_status');
            const result = await response.json();
            if (result.success) {
                return result.status;
            }
        } catch (error) {
            console.error('Error getting workflow monitor status:', error);
        }
        return null;
    }

    async toggleAutoDownload(enabled) {
        try {
            const response = await api.fetchApi('/filesystem/toggle_auto_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: enabled })
            });
            
            const result = await response.json();
            if (result.success) {
                this.workflowMonitor.enabled = enabled;
                // Update UI or notify user if needed
            }
        } catch (error) {
            console.error('Error toggling auto-download:', error);
        }
    }

    async updateGlobalModelDownloadProgress() {
        try {
            const response = await api.fetchApi('/filesystem/global_model_download_progress');
            const result = await response.json();
            
            if (result.success) {
                this.downloadProgress = result.progress;
                
                // Update UI elements for each global model
                for (const [modelPath, progress] of Object.entries(result.progress)) {
                    const modelElement = document.querySelector(`.fs-model-item[data-path="${modelPath}"]`);
                    if (modelElement) {
                        const progressBar = modelElement.querySelector('.fs-download-progress-bar');
                        if (progressBar) {
                            progressBar.style.width = `${progress.percentage}%`;
                            progressBar.setAttribute('aria-valuenow', progress.percentage);
                            
                            const progressText = modelElement.querySelector('.fs-download-progress-text');
                            if (progressText) {
                                progressText.textContent = `${progress.downloaded} / ${progress.total} (${progress.percentage}%)`;
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error updating global model download progress:', error);
        }
    }

    async handleGlobalModelDownload(item) {
        // Check for correct item properties
        if (item.global_exists && !item.local_exists && item.downloadable) {
            const modelPath = item.global_model_path || item.path;
            
            // Check if already downloading
            if (this.downloadProgress[modelPath] && 
                this.downloadProgress[modelPath].status === 'downloading') {
                // Already downloading
                UIComponents.showMessage(this.modal, `Already downloading ${modelPath}`, false);
                return;
            }
            
            try {
                UIComponents.showMessage(this.modal, `Starting download for ${modelPath}...`, false);
                  // Show initial progress UI
                    UIComponents.showGlobalModelProgress(this.modal, modelPath, {
                        status: 'downloading',
                        progress: 0,
                        downloaded_size: 0,
                        total_size: item.size || 0
                    });
                // Call the API to start the download
                const response = await api.fetchApi('/filesystem/download_global_model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_path: modelPath })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show initial progress UI
                    UIComponents.showGlobalModelProgress(this.modal, modelPath, {
                        status: 'downloading',
                        progress: 0,
                        downloaded_size: 0,
                        total_size: item.size || 0
                    });
                } else {
                    UIComponents.showMessage(this.modal, `Error: ${result.error || 'Failed to start download'}`, true);
                }
            } catch (error) {
                UIComponents.showMessage(this.modal, `Error: ${error.message}`, true);
            }
        }
    }

    async cancelGlobalModelDownload(modelPath) {
        try {
            const response = await api.fetchApi('/filesystem/cancel_global_model_download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_path: modelPath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                UIComponents.showMessage(this.modal, `Cancelled download for ${modelPath}`, false);
                UIComponents.hideGlobalModelProgress(this.modal, modelPath);
            } else {
                UIComponents.showMessage(this.modal, `Error: ${result.error || 'Failed to cancel download'}`, true);
            }
        } catch (error) {
            UIComponents.showMessage(this.modal, `Error: ${error.message}`, true);
        }
    }

    async updateGlobalModelDownloadProgress() {
        try {
            const response = await api.fetchApi('/filesystem/global_model_download_progress');
            const result = await response.json();
            
            if (result.success) {
                // Store the progress data
                this.downloadProgress = result.progress;
                
                // Update UI for each model in progress
                Object.entries(result.progress).forEach(([modelPath, progressData]) => {
                    UIComponents.showGlobalModelProgress(this.modal, modelPath, progressData);
                });
            }
        } catch (error) {
            console.error('Error updating global model download progress:', error);
        }
    }

    startGlobalModelDownloadProgress(modelPath) {
        const updateInterval = setInterval(async () => {
            try {
                const response = await api.fetchApi('/filesystem/global_model_download_progress');
                const result = await response.json();
                
                if (result.success) {
                    this.downloadProgress = result.progress;
                    
                    const progress = result.progress[modelPath];
                    if (progress) {
                        const modelElement = document.querySelector(`.fs-model-item[data-path="${modelPath}"]`);
                        if (modelElement) {
                            const progressBar = modelElement.querySelector('.fs-download-progress_bar');
                            if (progressBar) {
                                progressBar.style.width = `${progress.percentage}%`;
                                progressBar.setAttribute('aria-valuenow', progress.percentage);
                                
                                const progressText = modelElement.querySelector('.fs-download-progress_text');
                                if (progressText) {
                                    progressText.textContent = `${progress.downloaded} / ${progress.total} (${progress.percentage}%)`;
                                }
                            }
                        }
                        
                        if (progress.status === 'completed' || progress.status === 'error') {
                            clearInterval(updateInterval);
                        }
                    }
                }
            } catch (error) {
                console.error('Error updating global model download progress:', error);
                clearInterval(updateInterval);
            }
        }, 1000);
    }

    setupMissingModelsHandler() {
        // Set up a mutation observer to detect when missing models dialog appears
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if this is the missing models dialog
                        const missingModelsDialog = node.querySelector?.('.comfy-missing-models') || 
                                                  (node.classList?.contains('comfy-missing-models') ? node : null);
                        
                        if (missingModelsDialog) {
                            this.initializeMissingModelsDialog(node);
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    initializeMissingModelsDialog(dialogElement) {
        console.log('Missing models dialog detected, setting up download handlers');
        
        // Add custom CSS for better layout
        this.addMissingModelsStyles();
        
        // Find all download buttons in the dialog
        const downloadButtons = dialogElement.querySelectorAll('button[aria-label*="Download"]');
        
        downloadButtons.forEach((button, index) => {
            // Extract model information from the button and its parent elements
            const modelInfo = this.extractModelInfoFromButton(button);
            
            if (modelInfo) {
                // Store original click handler and replace with our custom handler
                const originalHandler = button.onclick;
                button.onclick = null;
                
                // Remove existing event listeners by cloning the button
                const newButton = button.cloneNode(true);
                button.parentNode.replaceChild(newButton, button);
                
                // Add our custom download handler
                newButton.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.handleMissingModelDownload(modelInfo, newButton);
                });
                
                // Improve the layout of the list item
                this.improveMissingModelLayout(newButton, modelInfo);
                
                // Add progress container for this model
                this.addProgressContainer(newButton, modelInfo);
            }
        });
    }

    addMissingModelsStyles() {
        // Add custom styles for missing models dialog if not already added
        if (document.querySelector('#missing-models-custom-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'missing-models-custom-styles';
        style.textContent = `
            .comfy-missing-models .p-listbox-option {
                padding: 16px !important;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
                transition: background-color 0.2s ease !important;
            }
            
            .comfy-missing-models .p-listbox-option:hover {
                background-color: rgba(255, 255, 255, 0.05) !important;
            }
            
            .fs-missing-model-container {
                display: flex;
                flex-direction: column;
                gap: 12px;
                width: 100%;
            }
            
            .fs-missing-model-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 12px;
            }
            
            .fs-missing-model-info {
                flex: 1;
                min-width: 0;
            }
            
            .fs-missing-model-title {
                font-weight: 600;
                font-size: 14px;
                color: var(--input-text);
                margin-bottom: 4px;
                word-break: break-word;
            }
            
            .fs-missing-model-path {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.7);
                font-family: monospace;
            }
            
            .fs-missing-model-actions {
                display: flex;
                gap: 8px;
                align-items: center;
                flex-shrink: 0;
            }
            
            .fs-missing-model-progress {
                margin-top: 8px;
                padding: 12px;
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                border-left: 3px solid #007bff;
            }
            
            .fs-progress-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 8px;
            }
            
            .fs-progress-text {
                color: var(--input-text);
                font-size: 12px;
                font-weight: 500;
            }
            
            .fs-progress-percentage {
                color: #007bff;
                font-size: 11px;
                font-weight: 600;
            }
            
            .fs-cancel-download {
                background: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                width: 20px;
                height: 20px;
                font-size: 10px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 0;
                transition: all 0.2s ease;
            }
            
            .fs-cancel-download:hover {
                background: #c82333;
                transform: scale(1.05);
            }
            
            .fs-progress-bar-container {
                width: 100%;
                height: 6px;
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                position: relative;
            }
            
            .fs-progress-bar-fill {
                height: 100%;
                background: linear-gradient(90deg, #007bff, #0056b3);
                transition: width 0.3s ease;
                border-radius: 3px;
                position: relative;
            }
            
            .fs-progress-bar-fill::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(
                    90deg,
                    transparent 0%,
                    rgba(255, 255, 255, 0.3) 50%,
                    transparent 100%
                );
                animation: shimmer 2s infinite;
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            .fs-download-complete {
                text-align: center;
                padding: 12px;
                font-weight: 600;
                color: #28a745;
                background-color: rgba(40, 167, 69, 0.1);
                border: 1px solid rgba(40, 167, 69, 0.3);
                border-radius: 6px;
            }
            
            .fs-download-error {
                text-align: center;
                padding: 12px;
                background-color: rgba(220, 53, 69, 0.1);
                border: 1px solid rgba(220, 53, 69, 0.3);
                border-radius: 6px;
            }
            
            .fs-download-error-text {
                color: #dc3545;
                font-size: 12px;
                margin-bottom: 8px;
            }
            
            .fs-retry-download {
                background: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 11px;
                padding: 6px 12px;
                transition: all 0.2s ease;
                font-weight: 500;
            }
            
            .fs-retry-download:hover {
                background: #0056b3;
                transform: translateY(-1px);
            }
            
            .comfy-missing-models button[aria-label*="Download"] {
                background: linear-gradient(135deg, #007bff, #0056b3) !important;
                color: white !important;
                border: none !important;
                padding: 8px 16px !important;
                border-radius: 6px !important;
                font-size: 12px !important;
                cursor: pointer !important;
                transition: all 0.2s ease !important;
                font-weight: 500 !important;
                box-shadow: 0 2px 4px rgba(0, 123, 255, 0.3) !important;
            }
            
            .comfy-missing-models button[aria-label*="Download"]:hover {
                background: linear-gradient(135deg, #0056b3, #004494) !important;
                transform: translateY(-1px) !important;
                box-shadow: 0 4px 8px rgba(0, 123, 255, 0.4) !important;
            }
            
            .comfy-missing-models button[aria-label*="Copy URL"] {
                background: rgba(108, 117, 125, 0.2) !important;
                color: var(--input-text) !important;
                border: 1px solid rgba(108, 117, 125, 0.5) !important;
                padding: 8px 16px !important;
                border-radius: 6px !important;
                font-size: 12px !important;
                cursor: pointer !important;
                transition: all 0.2s ease !important;
                font-weight: 500 !important;
            }
            
            .comfy-missing-models button[aria-label*="Copy URL"]:hover {
                background: rgba(108, 117, 125, 0.3) !important;
                transform: translateY(-1px) !important;
            }
        `;
        document.head.appendChild(style);
    }

    improveMissingModelLayout(button, modelInfo) {
        // Find the list item container
        const listItem = button.closest('li[role="option"]');
        if (!listItem) return;
        
        // Find the existing content div
        const existingContent = listItem.querySelector('div[data-v-7a5ec643]');
        if (!existingContent) return;
        
        // Create new structured layout
        const container = document.createElement('div');
        container.className = 'fs-missing-model-container';
        
        // Create header with model info and actions
        const header = document.createElement('div');
        header.className = 'fs-missing-model-header';
        
        // Model info section
        const infoSection = document.createElement('div');
        infoSection.className = 'fs-missing-model-info';
        
        const titleElement = document.createElement('div');
        titleElement.className = 'fs-missing-model-title';
        titleElement.textContent = modelInfo.filename;
        
        const pathElement = document.createElement('div');
        pathElement.className = 'fs-missing-model-path';
        pathElement.textContent = `${modelInfo.category}/${modelInfo.filename}`;
        
        infoSection.appendChild(titleElement);
        infoSection.appendChild(pathElement);
        
        // Actions section
        const actionsSection = document.createElement('div');
        actionsSection.className = 'fs-missing-model-actions';
        
        // Move existing buttons to actions section
        const downloadBtn = existingContent.querySelector('button[aria-label*="Download"]');
        const copyBtn = existingContent.querySelector('button[aria-label*="Copy URL"]');
        
        if (downloadBtn) actionsSection.appendChild(downloadBtn);
        if (copyBtn) actionsSection.appendChild(copyBtn);
        
        header.appendChild(infoSection);
        header.appendChild(actionsSection);
        container.appendChild(header);
        
        // Replace existing content
        existingContent.replaceWith(container);
    }

    addProgressContainer(button, modelInfo) {
        // Find the container
        const container = button.closest('.fs-missing-model-container');
        if (!container) return;
        
        // Create progress container
        const progressContainer = document.createElement('div');
        progressContainer.className = 'fs-missing-model-progress';
        progressContainer.style.display = 'none';
        progressContainer.innerHTML = `
            <div class="fs-progress-header">
                <span class="fs-progress-text">Preparing download...</span>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="fs-progress-percentage">0%</span>
                    <button class="fs-cancel-download" title="Cancel Download">×</button>
                </div>
            </div>
            <div class="fs-progress-bar-container">
                <div class="fs-progress-bar-fill" style="width: 0%"></div>
            </div>
        `;

        // Add to container
        container.appendChild(progressContainer);

        // Add cancel button handler
        const cancelBtn = progressContainer.querySelector('.fs-cancel-download');
        cancelBtn.addEventListener('click', () => {
            this.cancelMissingModelDownload(modelInfo);
        });
    }

    async handleMissingModelDownload(modelInfo, button) {
        console.log('Starting download for model:', modelInfo);

        // Find the progress container in the new layout
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        // Hide button and show progress
        button.style.display = 'none';
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }

        // Generate session ID
        const sessionId = `missing_model_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

        try {
            // Start progress polling
            this.startMissingModelProgressPolling(sessionId, modelInfo, button);
            // Call the direct upload endpoint
            const response = await api.fetchApi('/filesystem/upload_from_direct_url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    direct_url: modelInfo.url,
                    path: `models/${modelInfo.category}`,
                    filename: modelInfo.filename,
                    overwrite: true,
                    session_id: sessionId
                })
            });


            if (!response.ok) {
                const errorResult = await response.json();
                throw new Error(errorResult.error || `Request failed: ${response.statusText}`);
            }

        } catch (error) {
            console.error('Error starting model download:', error);
            this.showModelDownloadError(modelInfo, button, error.message);
        }
    }

    startMissingModelProgressPolling(sessionId, modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        const progressText = progressContainer?.querySelector('.fs-progress-text');
        const progressFill = progressContainer?.querySelector('.fs-progress-bar-fill');
        const progressPercentage = progressContainer?.querySelector('.fs-progress-percentage');

        // Always show the progress container while polling
        if (progressContainer) {
            progressContainer.style.display = 'block';
        }

        const pollInterval = setInterval(async () => {
            try {
                const response = await api.fetchApi(`/filesystem/direct_upload_progress/${sessionId}`);
                const progress = await response.json();

                // Update progress UI with enhanced feedback
                if (progressText) {
                    progressText.textContent = progress.message || 'Downloading...';
                }
                if (progressFill) {
                    const percentage = progress.percentage || 0;
                    progressFill.style.width = `${percentage}%`;
                }
                if (progressPercentage) {
                    progressPercentage.textContent = `${Math.round(progress.percentage || 0)}%`;
                }

                // Handle completion or error
                if (progress.status === 'completed') {
                    clearInterval(pollInterval);
                    this.showModelDownloadComplete(modelInfo, button);
                } else if (progress.status === 'error') {
                    clearInterval(pollInterval);
                    this.showModelDownloadError(modelInfo, button, progress.message);
                } else if (progress.status === 'cancelled') {
                    clearInterval(pollInterval);
                    this.resetModelDownloadUI(modelInfo, button);
                }

            } catch (error) {
                console.error('Error polling progress:', error);
                clearInterval(pollInterval);
                this.showModelDownloadError(modelInfo, button, 'Failed to check progress');
            }
        }, 500); // Poll every 500ms for more responsive updates

        // Store interval for potential cancellation
        modelInfo.pollInterval = pollInterval;
        modelInfo.sessionId = sessionId;
    }

    showModelDownloadComplete(modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.innerHTML = `
                <div class="fs-download-complete">
                    <span>✅ Download Complete</span>
                    <div style="font-size: 11px; margin-top: 4px; opacity: 0.8;">
                        ${modelInfo.filename} is now available
                    </div>
                </div>
            `;
            progressContainer.style.display = 'block';
        }
        button.style.display = 'none';
    }

    showModelDownloadError(modelInfo, button, errorMessage) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.innerHTML = `
                <div class="fs-download-error">
                    <div class="fs-download-error-text">❌ ${errorMessage}</div>
                    <button class="fs-retry-download">🔄 Retry Download</button>
                </div>
            `;
            progressContainer.style.display = 'block';

            // Add retry handler
            const retryBtn = progressContainer.querySelector('.fs-retry-download');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    this.resetModelDownloadUI(modelInfo, button);
                    // Trigger download again
                    this.handleMissingModelDownload(modelInfo, button);
                });
            }
        }
    }

    resetModelDownloadUI(modelInfo, button) {
        const container = button.closest('.fs-missing-model-container');
        const progressContainer = container?.querySelector('.fs-missing-model-progress');
        if (progressContainer) {
            progressContainer.style.display = 'none';
            // Reset progress container content
            progressContainer.innerHTML = `
                <div class="fs-progress-header">
                    <span class="fs-progress-text">Preparing download...</span>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="fs-progress-percentage">0%</span>
                        <button class="fs-cancel-download" title="Cancel Download">×</button>
                    </div>
                </div>
                <div class="fs-progress-bar-container">
                    <div class="fs-progress-bar-fill" style="width: 0%"></div>
                </div>
            `;
            
            // Re-attach cancel handler
            const cancelBtn = progressContainer.querySelector('.fs-cancel-download');
            cancelBtn.addEventListener('click', () => {
                this.cancelMissingModelDownload(modelInfo);
            });
        }
        button.style.display = 'inline-block';
        
        // Clean up polling
        if (modelInfo.pollInterval) {
            clearInterval(modelInfo.pollInterval);
            delete modelInfo.pollInterval;
        }
        delete modelInfo.sessionId;
    }

    extractModelInfoFromButton(button) {
        try {
            // Get the URL from title or aria-label
            const url = button.title || button.getAttribute('title');
            if (!url) return null;

            // Get model path and filename from the parent structure
            const listItem = button.closest('li[role="option"]');
            if (!listItem) return null;

            const modelSpan = listItem.querySelector('span[title]');
            if (!modelSpan) return null;

            const modelPath = modelSpan.textContent.trim();
            
            // Parse the model path (e.g., "checkpoints / dreamshaper_8.safetensors")
            const pathParts = modelPath.split(' / ');
            if (pathParts.length !== 2) return null;

            const [category, filename] = pathParts;
            const extension = filename.split('.').pop();
            const nameWithoutExt = filename.replace(`.${extension}`, '');

            // Extract file size from button text
            const sizeMatch = button.textContent.match(/\(([^)]+)\)/);
            const size = sizeMatch ? sizeMatch[1] : 'Unknown size';

            return {
                url: url.trim(),
                category: category.trim(),
                filename: filename.trim(),
                nameWithoutExt: nameWithoutExt,
                extension: extension,
                size: size,
                fullPath: `models/${category.trim()}/${filename.trim()}`
            };
        } catch (error) {
            console.error('Error extracting model info:', error);
            return null;
        }
    }

    async cancelMissingModelDownload(modelInfo) {
        console.log('Cancelling download for model:', modelInfo);
        
        try {
            if (modelInfo.sessionId) {
                // Send cancellation request to the server
                const response = await api.fetchApi('/filesystem/cancel_download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        session_id: modelInfo.sessionId,
                        download_type: 'direct-link'
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    console.log('Model download cancelled successfully');
                } else {
                    console.error('Failed to cancel model download:', result.error);
                }
            }
            
            // Clean up polling interval
            if (modelInfo.pollInterval) {
                clearInterval(modelInfo.pollInterval);
                delete modelInfo.pollInterval;
            }
            
            // Reset UI - find the button associated with this modelInfo
            const containers = document.querySelectorAll('.fs-missing-model-container');
            for (const container of containers) {
                const titleElement = container.querySelector('.fs-missing-model-title');
                if (titleElement && titleElement.textContent === modelInfo.filename) {
                    const button = container.querySelector('button[aria-label*="Download"]');
                    if (button) {
                        this.resetModelDownloadUI(modelInfo, button);
                        break;
                    }
                }
            }
            
        } catch (error) {
            console.error('Error cancelling model download:', error);
        }
    }
}