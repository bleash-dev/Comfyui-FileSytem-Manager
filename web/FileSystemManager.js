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
            (path) => this.navigateToPath(path), // Pass navigation handler for name links
            (item, triggerElement) => this.showItemContextMenu(item, triggerElement) // For action trigger
        );
        
        this.updateItemCount();
    }

    handleItemClick(item, e) {
        this.closeActiveContextMenu(); // Close context menu on any item click
        const itemPath = item.path;
        const isNameLinkClicked = e.target.closest('.fs-item-name-link');

        if (e.ctrlKey || e.metaKey) {
            this.toggleSelection(itemPath);
        } else {
            // If the name link was clicked, navigation is handled separately.
            // For selection purposes, a single click on the link or row behaves the same.
            this.selectItem(itemPath);
        }
        // If it's a directory and the name link was clicked, navigation is handled by the link's own event listener.
        // If it's a directory and other part of the row was clicked, it's just selected.
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
        } else {
            // Handle other types like 'civitai', 'direct-link'
            if (hasError) { // For non-GDrive, only URL is validated above
                UIComponents.showUploadMessage(this.uploadModal, errors.join(' '), true);
                // UIComponents.hideUploadProgress(this.uploadModal);
                return;
            }
            // For other types, you might have a generic filename input
            const commonFilenameInput = this.uploadModal.querySelector('#fs-upload-filename');
            if (commonFilenameInput) {
                 uploadData.filename = commonFilenameInput.value.trim();
            }
            // Add type-specific fields for Hugging Face, Civitai, etc.
            if (this.currentUploadType === 'huggingface') {
                // const token = this.uploadModal.querySelector('#fs-hf-token')?.value.trim(); // Token field removed
                // if (token) uploadData.token = token; // Token field removed
            } else if (this.currentUploadType === 'civitai') {
                const token = this.uploadModal.querySelector('#fs-civitai-token')?.value.trim();
                if (token) uploadData.token = token;
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

            // For CivitAI, Google Drive, and Hugging Face, let the poller handle the rest
            if (this.currentUploadType === 'civitai' || this.currentUploadType === 'google-drive' || this.currentUploadType === 'huggingface') {
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
}
