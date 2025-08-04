#!/usr/bin/env python3
"""
Debug test for decompression and symlink issues.
This test investigates what happens during the decompression process.
"""

import os
import sys
import tempfile
import subprocess
import tarfile
from pathlib import Path

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_test_archive_with_symlinks():
    """Create a test archive that contains symlinks to see how they're handled"""
    print("🔍 Testing archive creation and extraction with symlinks...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create source directory structure
        source_dir = temp_path / "source"
        source_dir.mkdir()
        
        # Create original files
        original_file = source_dir / "original_model.safetensors"
        original_file.write_text("This is the original model content for testing")
        
        # Create a symlink to the original file
        symlink_file = source_dir / "symlink_model.safetensors"
        symlink_file.symlink_to(original_file)
        
        print(f"📄 Created original file: {original_file} ({original_file.stat().st_size} bytes)")
        print(f"🔗 Created symlink: {symlink_file} -> {symlink_file.readlink()}")
        
        # Test 1: Create tar archive with default settings
        print("\n🗜️ Test 1: Creating tar.zst with default tar settings...")
        archive_default = temp_path / "test_default.tar.zst"
        
        # Create tar with symlinks preserved
        tar_cmd = ['tar', '-chf', '-', '-C', str(source_dir), '.']
        zstd_cmd = ['zstd', '-o', str(archive_default)]
        
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process = subprocess.Popen(zstd_cmd, stdin=tar_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process.stdout.close()
        
        zstd_output, zstd_error = zstd_process.communicate()
        tar_process.wait()
        
        if tar_process.returncode == 0 and zstd_process.returncode == 0:
            print(f"✅ Archive created: {archive_default} ({archive_default.stat().st_size} bytes)")
        else:
            print(f"❌ Archive creation failed")
            print(f"tar error: {tar_process.stderr.read().decode() if tar_process.stderr else 'None'}")
            print(f"zstd error: {zstd_error.decode() if zstd_error else 'None'}")
            return
        
        # Test 2: Extract and examine contents
        print("\n📦 Test 2: Extracting archive and examining contents...")
        extract_dir = temp_path / "extracted"
        extract_dir.mkdir()
        
        # Extract using our decompression method
        zstd_cmd = ['zstd', '-d', '-c', str(archive_default)]
        tar_cmd = ['tar', '-xf', '-', '-C', str(extract_dir)]
        
        zstd_process = subprocess.Popen(zstd_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process = subprocess.Popen(tar_cmd, stdin=zstd_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process.stdout.close()
        
        tar_output, tar_error = tar_process.communicate()
        zstd_process.wait()
        
        if tar_process.returncode == 0 and zstd_process.returncode == 0:
            print("✅ Archive extracted successfully")
        else:
            print("❌ Archive extraction failed")
            print(f"zstd error: {zstd_process.stderr.read().decode() if zstd_process.stderr else 'None'}")
            print(f"tar error: {tar_error.decode() if tar_error else 'None'}")
            return
        
        # Examine extracted contents
        print("\n🔍 Examining extracted contents...")
        for item in extract_dir.rglob('*'):
            if item.is_file():
                size = item.stat().st_size
                if item.is_symlink():
                    try:
                        target = item.readlink()
                        print(f"🔗 Symlink: {item.name} -> {target} ({size} bytes)")
                        
                        # Check if symlink is broken
                        try:
                            resolved = item.resolve()
                            actual_size = resolved.stat().st_size if resolved.exists() else "BROKEN"
                            print(f"   Resolved to: {resolved} (actual size: {actual_size})")
                        except (OSError, RuntimeError) as e:
                            print(f"   ❌ Cannot resolve symlink: {e}")
                    except OSError as e:
                        print(f"🔗 Symlink: {item.name} (cannot read target: {e}) ({size} bytes)")
                else:
                    print(f"📄 Regular file: {item.name} ({size} bytes)")
                    
                # Read and compare content
                try:
                    content = item.read_text()
                    print(f"   Content preview: '{content[:50]}{'...' if len(content) > 50 else ''}'")
                except (UnicodeDecodeError, OSError) as e:
                    print(f"   ❌ Cannot read content: {e}")
        
        # Test 3: Create archive without following symlinks (dereference)
        print("\n🗜️ Test 3: Creating tar.zst with symlinks dereferenced...")
        archive_deref = temp_path / "test_deref.tar.zst"
        
        # Create tar with symlinks dereferenced (follow symlinks)
        tar_cmd = ['tar', '-chf', '-', '-C', str(source_dir), '.']  # -h follows symlinks
        zstd_cmd = ['zstd', '-o', str(archive_deref)]
        
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process = subprocess.Popen(zstd_cmd, stdin=tar_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process.stdout.close()
        
        zstd_output, zstd_error = zstd_process.communicate()
        tar_process.wait()
        
        if tar_process.returncode == 0 and zstd_process.returncode == 0:
            print(f"✅ Dereferenced archive created: {archive_deref} ({archive_deref.stat().st_size} bytes)")
            
            # Extract and examine dereferenced archive
            extract_deref_dir = temp_path / "extracted_deref"
            extract_deref_dir.mkdir()
            
            zstd_cmd = ['zstd', '-d', '-c', str(archive_deref)]
            tar_cmd = ['tar', '-xf', '-', '-C', str(extract_deref_dir)]
            
            zstd_process = subprocess.Popen(zstd_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_process = subprocess.Popen(tar_cmd, stdin=zstd_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            zstd_process.stdout.close()
            
            tar_output, tar_error = tar_process.communicate()
            zstd_process.wait()
            
            if tar_process.returncode == 0 and zstd_process.returncode == 0:
                print("✅ Dereferenced archive extracted successfully")
                
                print("\n🔍 Examining dereferenced extracted contents...")
                for item in extract_deref_dir.rglob('*'):
                    if item.is_file():
                        size = item.stat().st_size
                        if item.is_symlink():
                            target = item.readlink()
                            print(f"🔗 Symlink: {item.name} -> {target} ({size} bytes)")
                        else:
                            print(f"📄 Regular file: {item.name} ({size} bytes)")
                            
                        # Read and compare content
                        try:
                            content = item.read_text()
                            print(f"   Content preview: '{content[:50]}{'...' if len(content) > 50 else ''}'")
                        except (UnicodeDecodeError, OSError) as e:
                            print(f"   ❌ Cannot read content: {e}")
        
        print("\n" + "="*60)
        print("🎯 Key Findings:")
        print("- Check if symlinks are being preserved or dereferenced")
        print("- Verify file sizes match expected values") 
        print("- Identify any corruption in the extraction process")
        print("="*60)

def test_simple_file_compression():
    """Test compression/decompression of a simple file without symlinks"""
    print("\n🧪 Testing simple file compression without symlinks...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a simple test file
        original_file = temp_path / "simple_model.safetensors"
        test_content = "Simple model content for testing compression without symlinks.\n" * 100
        original_file.write_text(test_content)
        
        original_size = original_file.stat().st_size
        print(f"📄 Created test file: {original_file} ({original_size} bytes)")
        
        # Compress it
        compressed_file = temp_path / "simple_model.tar.zst"
        
        tar_cmd = ['tar', '-cf', '-', '-C', str(temp_path), original_file.name]
        zstd_cmd = ['zstd', '-o', str(compressed_file)]
        
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process = subprocess.Popen(zstd_cmd, stdin=tar_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process.stdout.close()
        
        zstd_output, zstd_error = zstd_process.communicate()
        tar_process.wait()
        
        if tar_process.returncode != 0 or zstd_process.returncode != 0:
            print("❌ Compression failed")
            return
        
        compressed_size = compressed_file.stat().st_size
        print(f"🗜️ Compressed file: {compressed_file} ({compressed_size} bytes)")
        
        # Decompress it
        output_file = temp_path / "decompressed_simple.safetensors"
        extract_dir = temp_path / "extract"
        extract_dir.mkdir()
        
        zstd_cmd = ['zstd', '-d', '-c', str(compressed_file)]
        tar_cmd = ['tar', '-xf', '-', '-C', str(extract_dir)]
        
        zstd_process = subprocess.Popen(zstd_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process = subprocess.Popen(tar_cmd, stdin=zstd_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process.stdout.close()
        
        tar_output, tar_error = tar_process.communicate()
        zstd_process.wait()
        
        if tar_process.returncode != 0 or zstd_process.returncode != 0:
            print("❌ Decompression failed")
            print(f"zstd error: {zstd_process.stderr.read().decode() if zstd_process.stderr else 'None'}")
            print(f"tar error: {tar_error.decode() if tar_error else 'None'}")
            return
        
        # Find extracted file
        extracted_files = list(extract_dir.glob('*'))
        if not extracted_files:
            print("❌ No files extracted")
            return
        
        extracted_file = extracted_files[0]
        extracted_size = extracted_file.stat().st_size
        extracted_content = extracted_file.read_text()
        
        print(f"📤 Extracted file: {extracted_file} ({extracted_size} bytes)")
        
        # Verify integrity
        if original_size == extracted_size and test_content == extracted_content:
            print("✅ Simple file compression/decompression works correctly")
        else:
            print("❌ File corruption detected:")
            print(f"   Original size: {original_size}, Extracted size: {extracted_size}")
            print(f"   Content match: {test_content == extracted_content}")
            if test_content != extracted_content:
                print(f"   Original content start: '{test_content[:100]}'")
                print(f"   Extracted content start: '{extracted_content[:100]}'")

if __name__ == "__main__":
    print("🚀 Debugging Decompression and Symlink Issues")
    print("=" * 60)
    
    test_simple_file_compression()
    create_test_archive_with_symlinks()
