#!/usr/bin/env python3
"""
S3/R2 Compatible Client for ComfyUI File System Manager
Supports both AWS S3 and Cloudflare R2 with automatic failover and configuration detection
"""

import os
import json
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union, Callable, Any, List
from datetime import datetime

# Boto3 imports with fallback
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)


class S3ClientConfig:
    """Configuration class for S3/R2 client"""
    
    def __init__(self):
        self.provider = os.environ.get('S3_PROVIDER', 'aws').lower()
        self.bucket_name = os.environ.get('S3_BUCKET_NAME') or os.environ.get('AWS_BUCKET_NAME')
        self.region = os.environ.get('S3_REGION') or os.environ.get('AWS_REGION', 'us-east-1')
        self.access_key_id = os.environ.get('S3_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID')
        self.secret_access_key = os.environ.get('S3_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.endpoint_url = os.environ.get('S3_ENDPOINT_URL')
        
        # Provider-specific configuration
        if self.provider == 'cloudflare':
            # Cloudflare R2 configuration
            if not self.endpoint_url:
                self.endpoint_url = os.environ.get('CLOUDFLARE_R2_ENDPOINT')
            if not self.endpoint_url:
                account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID')
                if account_id:
                    self.endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        # Validate configuration
        self.is_valid = self._validate_config()
    
    def _validate_config(self) -> bool:
        """Validate S3 configuration"""
        required_fields = [self.bucket_name, self.access_key_id, self.secret_access_key]
        
        if not all(required_fields):
            logger.warning("Missing required S3 configuration fields")
            return False
        
        if self.provider == 'cloudflare' and not self.endpoint_url:
            logger.warning("Cloudflare R2 requires endpoint URL")
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            'provider': self.provider,
            'bucket_name': self.bucket_name,
            'region': self.region,
            'endpoint_url': self.endpoint_url,
            'is_valid': self.is_valid
        }


class S3ProgressCallback:
    """Progress callback handler for S3 operations"""
    
    def __init__(self, callback_func: Optional[Callable] = None, total_size: int = 0):
        self.callback_func = callback_func
        self.total_size = total_size
        self.bytes_transferred = 0
        self.last_update = 0
        self.update_interval = 0.1  # Update every 100ms
    
    def __call__(self, bytes_amount: int):
        """Called by boto3 during file transfer"""
        self.bytes_transferred += bytes_amount
        current_time = asyncio.get_event_loop().time()
        
        # Throttle updates to avoid overwhelming the UI
        if current_time - self.last_update >= self.update_interval:
            if self.callback_func:
                progress_percent = (self.bytes_transferred / self.total_size * 100) if self.total_size > 0 else 0
                self.callback_func(self.bytes_transferred, self.total_size, progress_percent)
            self.last_update = current_time


class S3Client:
    """Universal S3/R2 client supporting both AWS S3 and Cloudflare R2"""
    
    def __init__(self, config: Optional[S3ClientConfig] = None):
        self.config = config or S3ClientConfig()
        self.client = None
        self.is_connected = False
        self.connection_error = None
        
        if BOTO3_AVAILABLE and self.config.is_valid:
            self._initialize_client()
        else:
            logger.warning("S3 client initialization skipped - boto3 unavailable or invalid config")
    
    def _initialize_client(self):
        """Initialize boto3 S3 client"""
        try:
            # Configure boto3 client
            client_config = Config(
                region_name=self.config.region,
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                max_pool_connections=50
            )
            
            client_kwargs = {
                'aws_access_key_id': self.config.access_key_id,
                'aws_secret_access_key': self.config.secret_access_key,
                'config': client_config
            }
            
            # Add endpoint URL for non-AWS providers
            if self.config.endpoint_url:
                client_kwargs['endpoint_url'] = self.config.endpoint_url
            
            self.client = boto3.client('s3', **client_kwargs)
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            self.connection_error = str(e)
            logger.error(f"Failed to initialize S3 client: {e}")
    
    def _test_connection(self):
        """Test S3 connection by attempting to head the bucket"""
        try:
            self.client.head_bucket(Bucket=self.config.bucket_name)
            self.is_connected = True
            logger.info(f"✅ S3 client connected successfully (Provider: {self.config.provider})")
        except Exception as e:
            self.connection_error = str(e)
            logger.error(f"❌ S3 connection test failed: {e}")
            self.is_connected = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status and configuration info"""
        return {
            'connected': self.is_connected,
            'provider': self.config.provider,
            'bucket': self.config.bucket_name,
            'region': self.config.region,
            'endpoint_url': self.config.endpoint_url,
            'error': self.connection_error,
            'boto3_available': BOTO3_AVAILABLE,
            'config_valid': self.config.is_valid
        }
    
    def _parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """Parse S3 URI into bucket and key components"""
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)  # Remove 's3://' prefix
        if len(parts) < 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        return parts[0], parts[1]
    
    def _build_s3_uri(self, key: str, bucket: Optional[str] = None) -> str:
        """Build S3 URI from bucket and key"""
        bucket_name = bucket or self.config.bucket_name
        return f"s3://{bucket_name}/{key}"
    
    async def head_object(self, key: str, bucket: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get object metadata (size, modified date, etc.)"""
        if not self.is_connected:
            return None
        
        try:
            bucket_name = bucket or self.config.bucket_name
            response = self.client.head_object(Bucket=bucket_name, Key=key)
            
            return {
                'size': response.get('ContentLength', 0),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'content_type': response.get('ContentType', ''),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            logger.error(f"Error getting object metadata for {key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting object metadata for {key}: {e}")
            return None
    
    async def object_exists(self, key: str, bucket: Optional[str] = None) -> bool:
        """Check if an object exists in S3"""
        metadata = await self.head_object(key, bucket)
        return metadata is not None
    
    async def get_object_size(self, key: str, bucket: Optional[str] = None) -> Optional[int]:
        """Get object size in bytes"""
        metadata = await self.head_object(key, bucket)
        return metadata['size'] if metadata else None
    
    async def list_objects(self, prefix: str = '', bucket: Optional[str] = None, 
                          recursive: bool = True) -> List[Dict[str, Any]]:
        """List objects in bucket with optional prefix filter"""
        if not self.is_connected:
            return []
        
        try:
            bucket_name = bucket or self.config.bucket_name
            objects = []
            
            # Use paginator for large results
            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix=prefix,
                Delimiter='' if recursive else '/'
            )
            
            for page in page_iterator:
                # Regular objects
                for obj in page.get('Contents', []):
                    objects.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag'].strip('"'),
                        'type': 'file'
                    })
                
                # Directory prefixes (when not recursive)
                if not recursive:
                    for prefix_info in page.get('CommonPrefixes', []):
                        objects.append({
                            'key': prefix_info['Prefix'],
                            'type': 'directory'
                        })
            
            return objects
            
        except Exception as e:
            logger.error(f"Error listing objects with prefix {prefix}: {e}")
            return []
    
    async def download_file(self, key: str, local_path: Union[str, Path], 
                           bucket: Optional[str] = None,
                           progress_callback: Optional[Callable] = None,
                           chunk_size: int = 8192,
                           use_temp_dir: bool = True) -> bool:
        """Download file from S3 to local path with progress tracking and atomic operations"""
        if not self.is_connected:
            logger.error("S3 client not connected")
            return False
        
        try:
            bucket_name = bucket or self.config.bucket_name
            local_path = Path(local_path)
            
            # Ensure local directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get file size for progress tracking
            total_size = await self.get_object_size(key, bucket_name)
            
            # Create progress callback wrapper
            callback_wrapper = None
            if progress_callback and total_size:
                callback_wrapper = S3ProgressCallback(progress_callback, total_size)
            
            # Use local file's parent directory for temp files
            # (safer for cross-filesystem moves)
            temp_dir = local_path.parent
            
            # Download to temporary file first (atomic operation)
            with tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, prefix='s3_download_', suffix='.tmp') as temp_file:
                temp_path = Path(temp_file.name)
                
                try:
                    logger.debug(f"Downloading {key} to temporary file: {temp_path}")
                    
                    # Download using boto3
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None,
                        lambda: self.client.download_fileobj(
                            bucket_name, key, temp_file,
                            Callback=callback_wrapper
                        )
                    )
                    
                    # Verify download completed successfully
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                    
                    # Close the temp file before moving (required on Windows)
                    temp_file.close()
                    
                    # Verify file size if known
                    if total_size and temp_path.stat().st_size != total_size:
                        raise Exception(f"Downloaded file size mismatch: expected {total_size}, got {temp_path.stat().st_size}")
                    
                    # Move to final location (atomic)
                    if local_path.exists():
                        # Backup existing file
                        backup_path = local_path.with_suffix(local_path.suffix + '.backup')
                        local_path.rename(backup_path)
                        try:
                            temp_path.rename(local_path)
                            # Remove backup on success
                            backup_path.unlink()
                        except Exception as e:
                            # Restore backup on failure
                            if backup_path.exists():
                                backup_path.rename(local_path)
                            raise e
                    else:
                        temp_path.rename(local_path)
                    
                    logger.info(f"✅ Downloaded {key} to {local_path} (size: {local_path.stat().st_size} bytes)")
                    return True
                    
                except Exception as e:
                    # Clean up temp file on error
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to cleanup temp file {temp_path}: {cleanup_error}")
                    raise e
                    
        except Exception as e:
            logger.error(f"Error downloading {key}: {e}")
            return False
    
    async def upload_file(self, local_path: Union[str, Path], key: str,
                         bucket: Optional[str] = None,
                         progress_callback: Optional[Callable] = None,
                         metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file from local path to S3 with progress tracking"""
        if not self.is_connected:
            logger.error("S3 client not connected")
            return False
        
        try:
            bucket_name = bucket or self.config.bucket_name
            local_path = Path(local_path)
            
            if not local_path.exists():
                logger.error(f"Local file does not exist: {local_path}")
                return False
            
            # Get file size for progress tracking
            total_size = local_path.stat().st_size
            
            # Create progress callback wrapper
            callback_wrapper = None
            if progress_callback:
                callback_wrapper = S3ProgressCallback(progress_callback, total_size)
            
            # Prepare upload arguments
            upload_args = {}
            if metadata:
                upload_args['Metadata'] = metadata
            
            # Upload file
            with open(local_path, 'rb') as file_obj:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.client.upload_fileobj(
                        file_obj, bucket_name, key,
                        Callback=callback_wrapper,
                        ExtraArgs=upload_args
                    )
                )
            
            logger.info(f"✅ Uploaded {local_path} to {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading {local_path} to {key}: {e}")
            return False
    
    async def copy_object(self, source_key: str, dest_key: str,
                         source_bucket: Optional[str] = None,
                         dest_bucket: Optional[str] = None) -> bool:
        """Copy object within S3 or between buckets"""
        if not self.is_connected:
            logger.error("S3 client not connected")
            return False
        
        try:
            source_bucket = source_bucket or self.config.bucket_name
            dest_bucket = dest_bucket or self.config.bucket_name
            
            copy_source = {
                'Bucket': source_bucket,
                'Key': source_key
            }
            
            self.client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key
            )
            
            logger.info(f"✅ Copied {source_key} to {dest_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error copying {source_key} to {dest_key}: {e}")
            return False
    
    async def delete_object(self, key: str, bucket: Optional[str] = None) -> bool:
        """Delete object from S3"""
        if not self.is_connected:
            logger.error("S3 client not connected")
            return False
        
        try:
            bucket_name = bucket or self.config.bucket_name
            
            self.client.delete_object(Bucket=bucket_name, Key=key)
            logger.info(f"✅ Deleted {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting {key}: {e}")
            return False
    
    async def sync_directory_to_s3(self, local_dir: Union[str, Path], s3_prefix: str,
                                   bucket: Optional[str] = None,
                                   exclude_patterns: Optional[List[str]] = None,
                                   progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Sync local directory to S3 prefix"""
        if not self.is_connected:
            return {'success': False, 'error': 'S3 client not connected'}
        
        local_dir = Path(local_dir)
        if not local_dir.exists():
            return {'success': False, 'error': f'Local directory does not exist: {local_dir}'}
        
        try:
            bucket_name = bucket or self.config.bucket_name
            uploaded_files = []
            failed_files = []
            
            # Walk through local directory
            for local_file in local_dir.rglob('*'):
                if local_file.is_file():
                    # Calculate relative path and S3 key
                    relative_path = local_file.relative_to(local_dir)
                    s3_key = f"{s3_prefix.rstrip('/')}/{relative_path}"
                    
                    # Check exclude patterns
                    if exclude_patterns:
                        skip = any(pattern in str(relative_path) for pattern in exclude_patterns)
                        if skip:
                            continue
                    
                    # Upload file
                    success = await self.upload_file(local_file, s3_key, bucket_name, progress_callback)
                    if success:
                        uploaded_files.append(str(relative_path))
                    else:
                        failed_files.append(str(relative_path))
            
            return {
                'success': True,
                'uploaded_files': uploaded_files,
                'failed_files': failed_files,
                'total_uploaded': len(uploaded_files),
                'total_failed': len(failed_files)
            }
            
        except Exception as e:
            logger.error(f"Error syncing directory {local_dir} to S3: {e}")
            return {'success': False, 'error': str(e)}
    
    async def sync_directory_from_s3(self, s3_prefix: str, local_dir: Union[str, Path],
                                     bucket: Optional[str] = None,
                                     progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Sync S3 prefix to local directory"""
        if not self.is_connected:
            return {'success': False, 'error': 'S3 client not connected'}
        
        try:
            local_dir = Path(local_dir)
            local_dir.mkdir(parents=True, exist_ok=True)
            
            bucket_name = bucket or self.config.bucket_name
            downloaded_files = []
            failed_files = []
            
            # List all objects with the prefix
            objects = await self.list_objects(s3_prefix, bucket_name, recursive=True)
            
            for obj in objects:
                if obj['type'] == 'file':
                    # Calculate local file path
                    relative_key = obj['key'][len(s3_prefix.rstrip('/')) + 1:]
                    local_file_path = local_dir / relative_key
                    
                    # Download file
                    success = await self.download_file(obj['key'], local_file_path, bucket_name, progress_callback)
                    if success:
                        downloaded_files.append(relative_key)
                    else:
                        failed_files.append(relative_key)
            
            return {
                'success': True,
                'downloaded_files': downloaded_files,
                'failed_files': failed_files,
                'total_downloaded': len(downloaded_files),
                'total_failed': len(failed_files)
            }
            
        except Exception as e:
            logger.error(f"Error syncing S3 prefix {s3_prefix} to directory {local_dir}: {e}")
            return {'success': False, 'error': str(e)}


# Global S3 client instance
_global_s3_client: Optional[S3Client] = None


def get_s3_client(config: Optional[S3ClientConfig] = None) -> S3Client:
    """Get global S3 client instance (singleton pattern)"""
    global _global_s3_client
    
    if _global_s3_client is None or config is not None:
        _global_s3_client = S3Client(config)
    
    return _global_s3_client


def reset_s3_client():
    """Reset global S3 client (useful for testing or config changes)"""
    global _global_s3_client
    _global_s3_client = None


# Convenience functions for common operations
async def s3_download(key: str, local_path: Union[str, Path], 
                     progress_callback: Optional[Callable] = None) -> bool:
    """Convenience function for downloading files"""
    client = get_s3_client()
    return await client.download_file(key, local_path, progress_callback=progress_callback)


async def s3_upload(local_path: Union[str, Path], key: str,
                   progress_callback: Optional[Callable] = None) -> bool:
    """Convenience function for uploading files"""
    client = get_s3_client()
    return await client.upload_file(local_path, key, progress_callback=progress_callback)


async def s3_exists(key: str) -> bool:
    """Convenience function for checking if object exists"""
    client = get_s3_client()
    return await client.object_exists(key)


async def s3_size(key: str) -> Optional[int]:
    """Convenience function for getting object size"""
    client = get_s3_client()
    return await client.get_object_size(key)


async def s3_list(prefix: str = '', recursive: bool = True) -> List[Dict[str, Any]]:
    """Convenience function for listing objects"""
    client = get_s3_client()
    return await client.list_objects(prefix, recursive=recursive)


# Example usage and testing functions
async def test_s3_connectivity():
    """Test S3 connectivity and basic operations"""
    client = get_s3_client()
    status = client.get_status()
    
    print("🔍 S3 Client Status:")
    print(json.dumps(status, indent=2, default=str))
    
    if not status['connected']:
        print("❌ S3 client not connected")
        return False
    
    # Test basic operations
    try:
        # Test listing objects
        objects = await client.list_objects('', recursive=False)
        print(f"✅ Successfully listed {len(objects)} objects")
        
        return True
        
    except Exception as e:
        print(f"❌ S3 connectivity test failed: {e}")
        return False


if __name__ == "__main__":
    # Run connectivity test if script is executed directly
    asyncio.run(test_s3_connectivity())
