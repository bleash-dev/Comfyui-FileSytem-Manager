# Array Format Update for get_downloadable_models

## Change Summary

Updated the `get_initial_models_list()` method in `InitialModelsSyncManager` to handle the new array format returned by the shell command `get_downloadable_models`.

## Previous Format (Object with nested groups)
```json
{
  "group1": {
    "model1": { "modelName": "model1", "groupName": "group1", ... },
    "model2": { "modelName": "model2", "groupName": "group1", ... }
  },
  "group2": {
    "model3": { "modelName": "model3", "groupName": "group2", ... }
  }
}
```

## New Format (Array with groupName in each item)
```json
[
  { "modelName": "model1", "groupName": "group1", "originalS3Path": "...", "localPath": "...", ... },
  { "modelName": "model2", "groupName": "group1", "originalS3Path": "...", "localPath": "...", ... },
  { "modelName": "model3", "groupName": "group2", "originalS3Path": "...", "localPath": "...", ... }
]
```

## Code Changes

**Before:**
```python
for group_name, group_models in all_models.items():
    group_to_sync = {}
    for model_name, model_data in group_models.items():
        # Process model_data
```

**After:**
```python
for model_data in all_models:
    group_name = (model_data.get('groupName') or
                  model_data.get('directoryGroup', 'Unknown'))
    model_name = model_data.get('modelName', 'Unknown')
    
    # Initialize group if not exists
    if group_name not in models_to_sync:
        models_to_sync[group_name] = {}
    
    # Process model_data
```

## Expected Model Data Properties

Each model object in the array should contain:
- `modelName`: The name/identifier of the model
- `groupName` or `directoryGroup`: The group/category this model belongs to  
- `originalS3Path`: The S3 path where the model is stored
- `localPath`: The local file system path where the model should be downloaded
- `modelSize`: Size of the model file in bytes
- `downloadSource`: Optional, defaults to 's3'
- `downloadUrl`: Optional, defaults to originalS3Path

## Backward Compatibility

The code now handles the `groupName` property primarily, but falls back to `directoryGroup` for compatibility, and uses 'Unknown' as a final fallback if neither is present.

## Output Format

The method still returns the same grouped structure for the frontend:
```json
{
  "success": true,
  "models": {
    "group1": {
      "model1": { ... },
      "model2": { ... }
    },
    "group2": {
      "model3": { ... }
    }
  },
  "totalModels": 3,
  "totalSize": 12345,
  "formattedSize": "12.1 KB"
}
```

This ensures the frontend continues to work without any changes while supporting the new shell script array format.
