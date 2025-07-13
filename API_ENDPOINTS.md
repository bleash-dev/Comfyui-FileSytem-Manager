# ComfyUI File System Manager API Endpoints

This document lists all the available REST API endpoints for the ComfyUI File System Manager.

## Model Download and Management Endpoints

### Google Drive Downloads
- `POST /filesystem/upload_from_google_drive` - Download from Google Drive
- `GET /filesystem/google_drive_progress/{session_id}` - Get Google Drive download progress

### HuggingFace Downloads
- `POST /filesystem/download_from_huggingface` - Download from HuggingFace
- `GET /filesystem/huggingface_progress/{session_id}` - Get HuggingFace download progress

### CivitAI Downloads
- `POST /filesystem/download_from_civitai` - Download from CivitAI
- `GET /filesystem/civitai_progress/{session_id}` - Get CivitAI download progress

### Direct URL Downloads
- `POST /filesystem/download_from_url` - Download from direct URL
- `GET /filesystem/direct_download_progress/{session_id}` - Get direct download progress

### Missing Models Handler
- `POST /filesystem/resolve_missing_models` - Resolve missing models
- `GET /filesystem/missing_models_progress/{session_id}` - Get missing models resolution progress

## File System Operations

### Directory and File Management
- `GET /filesystem/browse` - Browse directory contents
- `POST /filesystem/create_directory` - Create a new directory
- `DELETE /filesystem/delete` - Delete files or directories
- `GET /filesystem/file_info` - Get file information
- `POST /filesystem/rename` - Rename files or directories

### File Downloads
- `GET /filesystem/download_file` - Download a single file
- `POST /filesystem/download_multiple` - Download multiple files as ZIP

## Sync Management Endpoints

### Sync Operations
- `GET /filesystem/sync/status` - Get sync manager status
- `POST /filesystem/sync/unlock` - Unlock sync manager
- `POST /filesystem/sync/test` - Test sync configuration
- `POST /filesystem/sync/run` - Run specific sync operation
- `POST /filesystem/sync/run_all` - Run all sync operations
- `GET /filesystem/sync/list` - List available sync operations
- `GET /filesystem/sync/logs/{sync_type}` - Get logs for specific sync type

### Legacy Sync
- `POST /filesystem/sync_new_model` - Legacy sync new model endpoint

## Workflow Execution Endpoints

### Workflow Management
- `POST /filesystem/workflow/execute` - Start workflow execution
- `GET /filesystem/workflow/status/{execution_id}` - Get workflow execution status
- `POST /filesystem/workflow/cancel` - Cancel workflow execution

## Model Configuration

All download handlers automatically register downloaded models in the central model configuration (`models_config.json`). This includes:

- **S3 Downloads**: Registered with S3 source information
- **HuggingFace Downloads**: Individual files and complete repositories
- **CivitAI Downloads**: With model and version IDs
- **Google Drive Downloads**: With drive URL information
- **Direct URL Downloads**: With source URL
- **Symlinked Models**: Tracked with `symLinkedFrom` field

### Model Type Detection

The system automatically detects model types based on:
1. Directory structure (e.g., `/models/checkpoints/`, `/models/loras/`)
2. File location within repositories
3. Explicit type specification in API calls

### Bulk Repository Registration

When downloading complete HuggingFace repositories, all files (`.safetensors`, `.pt`, `.pth`, `.ckpt`, `.bin`, `.json`, `.yml`, `.yaml`, `.py`, `.txt`, `.md`) are automatically registered with appropriate metadata.

**Important**: Repository files are registered in the **ComfyUI models group** where they were downloaded, preserving the original repository structure within that group.

#### Repository Registration Logic:
- **Group Detection**: Files are grouped based on their download location in the ComfyUI models directory structure
- **Structure Preservation**: Original repository directory structure is maintained within each group
- **Fallback Grouping**: If downloaded outside standard ComfyUI models folders, files are grouped under `repositories/REPO_NAME`

#### Examples:

**Repository downloaded to `/ComfyUI/models/checkpoints/stable-diffusion-v1-5/`:**
```json
{
  "checkpoints": [
    {
      "localPath": "/ComfyUI/models/checkpoints/stable-diffusion-v1-5/model_index.json",
      "repositoryPath": "model_index.json",
      "repositoryId": "runwayml/stable-diffusion-v1-5"
    },
    {
      "localPath": "/ComfyUI/models/checkpoints/stable-diffusion-v1-5/unet/diffusion_pytorch_model.bin",
      "repositoryPath": "unet/diffusion_pytorch_model.bin", 
      "repositoryId": "runwayml/stable-diffusion-v1-5"
    }
  ]
}
```

**Repository downloaded to `/ComfyUI/models/loras/xl-lora-pack/`:**
```json
{
  "loras": [
    {
      "localPath": "/ComfyUI/models/loras/xl-lora-pack/pytorch_lora_weights.safetensors",
      "repositoryPath": "pytorch_lora_weights.safetensors",
      "repositoryId": "some-user/xl-lora-pack"
    }
  ]
}
```

#### Registration Features:
- **Complete File Registration**: All relevant files in the repository are tracked
- **Model Group Integration**: Files appear alongside other models of the same type
- **Metadata Tracking**: Includes repository ID, relative path within repo, and download source
- **Source URL Tracking**: Records the original download URL

## Error Handling

All endpoints return consistent JSON responses with:
- `success`: Boolean indicating operation success
- `message`: Human-readable message
- `error`: Error details (when success is false)
- `data`: Response data (when applicable)

## Authentication and Security

- Endpoints require proper ComfyUI server authentication
- File operations are restricted to configured safe directories
- Download cancellation is supported via session IDs
- Progress tracking is session-based for security

## Integration Points

### Shell Script Integration
- Sync manager operations call external shell scripts
- Model configuration uses `model_config_manager.sh`
- Workflow execution integrates with external workflow management

### Background Processing
- Long-running downloads use background tasks
- Progress is tracked and can be queried
- Operations can be cancelled via session management

## Usage Examples

### Download from HuggingFace Repository
```bash
curl -X POST http://localhost:8188/filesystem/download_from_huggingface \
  -H "Content-Type: application/json" \
  -d '{
    "hf_url": "https://huggingface.co/runwayml/stable-diffusion-v1-5",
    "target_path": "/models/checkpoints/",
    "overwrite": false
  }'
```

### Execute Workflow
```bash
curl -X POST http://localhost:8188/filesystem/workflow/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow": {...},
    "client_id": "client-123"
  }'
```

### Run Sync Operation
```bash
curl -X POST http://localhost:8188/filesystem/sync/run \
  -H "Content-Type: application/json" \
  -d '{
    "sync_type": "s3_download",
    "options": {...}
  }'
```
