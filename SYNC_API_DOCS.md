# Sync Manager API Endpoints

This document describes the sync management API endpoints that have been integrated into the ComfyUI File System Manager.

## Overview

The sync manager integration provides REST API endpoints to manage and monitor sync operations across different data types in the ComfyUI environment. It interfaces with the `sync_manager.sh` script at runtime.

## Available Endpoints

### 1. Get Sync Status
**GET** `/filesystem/sync/status`

Get the current status of all sync operations.

**Response:**
```json
{
  "success": true,
  "status": "retrieved",
  "output": "Status output from sync manager",
  "message": "Sync status retrieved successfully"
}
```

### 2. Force Unlock Sync
**POST** `/filesystem/sync/unlock`

Force release sync locks (all or specific type).

**Request Body:**
```json
{
  "sync_type": "user_data"  // Optional - omit to unlock all
}
```

**Response:**
```json
{
  "success": true,
  "status": "unlocked", 
  "output": "Unlock output",
  "message": "Successfully unlocked user_data sync locks"
}
```

### 3. Test Sync Lock
**POST** `/filesystem/sync/test`

Test the sync lock mechanism for debugging.

**Request Body:**
```json
{
  "sync_type": "test_sync"  // Optional - defaults to "test_sync"
}
```

**Response:**
```json
{
  "success": true,
  "status": "test_passed",
  "output": "Test output",
  "message": "Sync lock test passed for test_sync"
}
```

### 4. Run Specific Sync
**POST** `/filesystem/sync/run`

Run a specific sync operation.

**Request Body:**
```json
{
  "sync_type": "user_data"  // Required
}
```

**Response:**
```json
{
  "success": true,
  "status": "completed",
  "sync_type": "user_data",
  "output": "Sync output",
  "message": "Successfully ran user_data sync"
}
```

### 5. Run All Syncs
**POST** `/filesystem/sync/run_all`

Run all sync operations sequentially.

**Request Body:** Empty

**Response:**
```json
{
  "success": true,
  "status": "completed",
  "total_syncs": 5,
  "successful_syncs": ["user_data", "user_shared", "global_shared", "user_assets", "logs"],
  "failed_syncs": [],
  "detailed_results": {
    "user_data": { "success": true, ... },
    "user_shared": { "success": true, ... }
  },
  "message": "All syncs completed successfully"
}
```

### 6. List Sync Scripts
**GET** `/filesystem/sync/list`

List all available sync scripts and their status.

**Response:**
```json
{
  "success": true,
  "status": "retrieved",
  "output": "Script listing output",
  "available_syncs": ["user_data", "user_shared", "global_shared", "user_assets", "logs"],
  "message": "Successfully retrieved sync scripts list"
}
```

### 7. Get Sync Logs
**GET** `/filesystem/sync/logs/{sync_type}?lines=20`

Get recent logs for a specific sync type.

**Path Parameters:**
- `sync_type`: The type of sync to get logs for

**Query Parameters:**
- `lines`: Number of log lines to retrieve (default: 20)

**Response:**
```json
{
  "success": true,
  "status": "retrieved",
  "sync_type": "user_data",
  "lines_requested": 20,
  "output": "Log content",
  "message": "Successfully retrieved user_data logs"
}
```

## Sync Types

The following sync types are supported:

- **user_data** - Pod-specific user data sync
- **user_shared** - User-shared data sync (across pods)  
- **global_shared** - Global shared models and browser sessions
- **user_assets** - ComfyUI input/output assets
- **logs** - System and application logs

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error description",
  "message": "Human-readable error message"
}
```

Common HTTP status codes:
- **200** - Success
- **400** - Bad request (missing required parameters)
- **500** - Internal server error
- **503** - Service unavailable (sync manager not available)

## Usage Examples

### Using curl

```bash
# Get sync status
curl -X GET http://localhost:8188/filesystem/sync/status

# Run user data sync
curl -X POST http://localhost:8188/filesystem/sync/run \
  -H "Content-Type: application/json" \
  -d '{"sync_type": "user_data"}'

# Run all syncs
curl -X POST http://localhost:8188/filesystem/sync/run_all

# Force unlock all locks
curl -X POST http://localhost:8188/filesystem/sync/unlock \
  -H "Content-Type: application/json" \
  -d '{}'

# Get logs for global shared sync
curl -X GET "http://localhost:8188/filesystem/sync/logs/global_shared?lines=50"
```

### Using JavaScript/Fetch

```javascript
// Run all syncs
async function runAllSyncs() {
  const response = await fetch('/filesystem/sync/run_all', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });
  
  const result = await response.json();
  console.log('Sync results:', result);
}

// Get sync status
async function getSyncStatus() {
  const response = await fetch('/filesystem/sync/status');
  const status = await response.json();
  console.log('Sync status:', status);
}
```

## Integration Notes

- All sync operations run asynchronously to avoid blocking the API
- The sync manager uses file-based locking to prevent concurrent operations
- Long-running sync operations have appropriate timeouts (up to 10 minutes)
- Detailed logging is available for troubleshooting
- The API gracefully handles cases where the sync manager script is not available

## Dependencies

- Requires `sync_manager.sh` script to be available at `$NETWORK_VOLUME/scripts/sync_manager.sh`
- Depends on the sync lock manager and individual sync scripts
- Uses the existing ComfyUI PromptServer for routing
