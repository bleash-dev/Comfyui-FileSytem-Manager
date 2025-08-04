#!/usr/bin/env python3
"""
Test the actual GlobalModelsManager decompression method to reproduce the corruption issue.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from global_models_manager import GlobalModelsManager
    print("✅ Successfully imported GlobalModelsManager")
except ImportError as e:
    print(f"❌ Failed to import GlobalModelsManager: {e}")
    sys.exit(1)

async def test_actual_decompression():
    """Test the actual decompression method to identify corruption issues"""
    print("🔍 Testing actual GlobalModelsManager decompression...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a test file with known content
        test_content = "Test model file content.\nThis is line 2.\nThis is line 3.\n" * 100
        original_file = temp_path / "test_model.safetensors"
        original_file.write_text(test_content)
        original_size = original_file.stat().st_size
        
        print(f"📄 Created test file: {original_size} bytes")
        print(f"🔑 Content hash: {hash(test_content)}")
        
        # Compress manually using the same method as our system
        compressed_file = temp_path / "test_model.tar.zst"
        
        # Use the exact same compression as the system would
        tar_cmd = ['tar', '-chf', '-', '-C', str(temp_path), original_file.name]
        zstd_cmd = ['zstd', '-o', str(compressed_file)]
        
        print("🗜️ Compressing file...")
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process = subprocess.Popen(zstd_cmd, stdin=tar_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_process.stdout.close()
        
        zstd_output, zstd_error = zstd_process.communicate()
        tar_process.wait()
        
        if tar_process.returncode != 0 or zstd_process.returncode != 0:
            print("❌ Compression failed")
            return
        
        compressed_size = compressed_file.stat().st_size
        print(f"✅ Compressed to: {compressed_size} bytes")
        
        # Now test decompression using GlobalModelsManager
        print("\n🔄 Testing GlobalModelsManager decompression...")
        manager = GlobalModelsManager()
        
        decompressed_file = temp_path / "decompressed_model.safetensors"
        
        success = await manager._decompress_file(str(compressed_file), str(decompressed_file))
        
        if not success:
            print("❌ Decompression failed")
            return
        
        if not decompressed_file.exists():
            print("❌ Decompressed file does not exist")
            return
        
        # Check the decompressed file
        decompressed_size = decompressed_file.stat().st_size
        print(f"📤 Decompressed file size: {decompressed_size} bytes")
        
        try:
            decompressed_content = decompressed_file.read_text()
            print(f"🔑 Decompressed content hash: {hash(decompressed_content)}")
            
            # Compare sizes
            if original_size == decompressed_size:
                print("✅ File size matches")
            else:
                print(f"❌ Size mismatch: {original_size} vs {decompressed_size}")
            
            # Compare content
            if test_content == decompressed_content:
                print("✅ Content matches perfectly")
            else:
                print("❌ Content corruption detected!")
                print(f"   Original length: {len(test_content)}")
                print(f"   Decompressed length: {len(decompressed_content)}")
                
                # Show first difference
                for i, (o, d) in enumerate(zip(test_content, decompressed_content)):
                    if o != d:
                        print(f"   First difference at position {i}: '{o}' vs '{d}'")
                        break
                
                # Show first 200 chars of each
                print(f"   Original start: '{test_content[:200]}'")
                print(f"   Decompressed start: '{decompressed_content[:200]}'")
                
        except UnicodeDecodeError as e:
            print(f"❌ Cannot read decompressed file as text: {e}")
            # Try reading as binary
            try:
                decompressed_bytes = decompressed_file.read_bytes()
                original_bytes = original_file.read_bytes()
                
                print(f"📊 Binary comparison:")
                print(f"   Original bytes: {len(original_bytes)}")
                print(f"   Decompressed bytes: {len(decompressed_bytes)}")
                
                if original_bytes == decompressed_bytes:
                    print("✅ Binary content matches")
                else:
                    print("❌ Binary content differs")
                    
                    # Find first difference
                    for i, (o, d) in enumerate(zip(original_bytes, decompressed_bytes)):
                        if o != d:
                            print(f"   First byte difference at position {i}: {o} vs {d}")
                            break
                            
            except Exception as e2:
                print(f"❌ Cannot read decompressed file as binary: {e2}")

async def test_compression_extraction_steps():
    """Test each step of the compression/extraction process separately"""
    print("\n🔬 Testing compression extraction steps separately...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test file
        test_content = "Step-by-step test content.\n" * 50
        original_file = temp_path / "step_test.safetensors"
        original_file.write_text(test_content)
        
        print(f"📄 Original file: {original_file.stat().st_size} bytes")
        
        # Step 1: Create tar file (no compression)
        tar_file = temp_path / "step_test.tar"
        tar_cmd = ['tar', '-cf', str(tar_file), '-C', str(temp_path), original_file.name]
        
        result = subprocess.run(tar_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Tar creation failed: {result.stderr}")
            return
        
        print(f"📦 Tar file: {tar_file.stat().st_size} bytes")
        
        # Step 2: Compress tar with zstd
        compressed_file = temp_path / "step_test.tar.zst"
        zstd_cmd = ['zstd', str(tar_file), '-o', str(compressed_file)]
        
        result = subprocess.run(zstd_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Zstd compression failed: {result.stderr}")
            return
        
        print(f"🗜️ Compressed file: {compressed_file.stat().st_size} bytes")
        
        # Step 3: Decompress with zstd
        decompressed_tar = temp_path / "step_test_decompressed.tar"
        zstd_cmd = ['zstd', '-d', str(compressed_file), '-o', str(decompressed_tar)]
        
        result = subprocess.run(zstd_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Zstd decompression failed: {result.stderr}")
            return
        
        print(f"📤 Decompressed tar: {decompressed_tar.stat().st_size} bytes")
        
        # Step 4: Extract from tar
        extract_dir = temp_path / "extracted"
        extract_dir.mkdir()
        
        tar_cmd = ['tar', '-xf', str(decompressed_tar), '-C', str(extract_dir)]
        
        result = subprocess.run(tar_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Tar extraction failed: {result.stderr}")
            return
        
        # Check extracted file
        extracted_files = list(extract_dir.glob('*'))
        if not extracted_files:
            print("❌ No files extracted")
            return
        
        extracted_file = extracted_files[0]
        extracted_content = extracted_file.read_text()
        
        print(f"📄 Extracted file: {extracted_file.stat().st_size} bytes")
        
        if test_content == extracted_content:
            print("✅ Step-by-step process works correctly")
        else:
            print("❌ Step-by-step process has corruption")

async def main():
    print("🚀 Debugging Actual Decompression Issues")
    print("=" * 60)
    
    await test_actual_decompression()
    await test_compression_extraction_steps()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
