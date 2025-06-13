export class Dialog {
    static show({
        title = 'Confirm',
        message = '',
        buttons = ['Cancel', 'OK'],
        defaultButton = 0,
        type = 'default' // 'default', 'warning', 'danger'
    }) {
        return new Promise((resolve) => {
            const dialog = this.createDialog({
                title,
                message,
                buttons,
                defaultButton,
                type,
                onResult: resolve
            });
            
            document.body.appendChild(dialog);
            
            // Focus the default button
            const buttonElements = dialog.querySelectorAll('.fs-dialog-btn');
            if (buttonElements[defaultButton]) {
                buttonElements[defaultButton].focus();
            }
        });
    }

    static createDialog({ title, message, buttons, defaultButton, type, onResult }) {
        const overlay = document.createElement('div');
        overlay.className = 'fs-dialog-overlay';
        
        const dialog = document.createElement('div');
        dialog.className = `fs-dialog fs-dialog-${type}`;
        
        dialog.innerHTML = `
            <div class="fs-dialog-header">
                <h4 class="fs-dialog-title">${this.escapeHtml(title)}</h4>
            </div>
            <div class="fs-dialog-content">
                <p class="fs-dialog-message">${this.escapeHtml(message)}</p>
            </div>
            <div class="fs-dialog-actions">
                ${buttons.map((buttonText, index) => 
                    `<button class="fs-btn fs-dialog-btn ${this.getButtonClass(type, index, defaultButton, buttons)}" 
                             data-result="${index}">
                        ${this.escapeHtml(buttonText)}
                     </button>`
                ).join('')}
            </div>
        `;
        
        overlay.appendChild(dialog);
        
        // Event listeners
        const handleResult = (result) => {
            document.body.removeChild(overlay);
            onResult(result);
        };
        
        // Button clicks
        dialog.addEventListener('click', (e) => {
            if (e.target.classList.contains('fs-dialog-btn')) {
                const result = parseInt(e.target.dataset.result);
                handleResult(result);
            }
        });
        
        // Keyboard handling
        overlay.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                handleResult(0); // Cancel
            } else if (e.key === 'Enter') {
                handleResult(defaultButton);
            }
        });
        
        // Backdrop click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                handleResult(0); // Cancel
            }
        });
        
        return overlay;
    }
    
    static getButtonClass(type, index, defaultButton, buttons) {
        const baseClass = index === defaultButton ? 'fs-btn-primary' : 'fs-btn-secondary';
        
        if (type === 'danger' && index === buttons.length - 1) {
            return 'fs-btn-danger';
        }
        
        return baseClass;
    }
    
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
