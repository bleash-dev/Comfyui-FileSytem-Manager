import { app } from "../../scripts/app.js";
import { FileSystemManager } from "./FileSystemManager.js";
import { MissingModelsManager } from "./MissingModelsManager.js";
import "./styles.js";

// Create global instances
const fileSystemManager = new FileSystemManager();
const missingModelsManager = new MissingModelsManager();

// Make them globally available for debugging
window.fileSystemManager = fileSystemManager;
window.missingModelsManager = missingModelsManager;

// Add button to ComfyUI interface
app.registerExtension({
    name: "FileSystemManager",
    async setup() {
        console.log("🚀 File System Manager Extension Loading");
        
        // Add file manager button to the top menu bar
        const menu = document.querySelector('.comfyui-menu-right');
        if (menu) {
            const fileManagerBtn = document.createElement('button');
            fileManagerBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="20px" height="20px" viewBox="0 0 24 24" fill="none">
                    <path d="M3 8L3 18C3 19.1046 3.89543 20 5 20L19 20C20.1046 20 21 19.1046 21 18L21 10C21 8.89543 20.1046 8 19 8L11 8L9 6L5 6C3.89543 6 3 6.89543 3 8Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
            fileManagerBtn.title = 'File System Manager';
            fileManagerBtn.style.cssText = `
                background: none;
                border: none;
                padding: 8px;
                margin: 0 4px;
                cursor: pointer;
                color: var(--input-text);
                display: inline-flex;
                align-items: center;
                justify-content: center;
                vertical-align: middle;
                border-radius: 4px;
                transition: background-color 0.2s ease;
            `;
            
            // Add hover effect
            fileManagerBtn.addEventListener('mouseenter', () => {
                fileManagerBtn.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
            });
            
            fileManagerBtn.addEventListener('mouseleave', () => {
                fileManagerBtn.style.backgroundColor = 'transparent';
            });
            
            fileManagerBtn.addEventListener('click', () => {
                console.log("📁 File System Manager button clicked");
                fileSystemManager.showModal();
            });
            
            menu.appendChild(fileManagerBtn);
            console.log("✅ File System Manager button added to menu");
        } else {
            console.warn("⚠️ Could not find ComfyUI menu to add File System Manager button");
        }
        
        console.log("✅ File System Manager Extension Loaded");
    }
});
