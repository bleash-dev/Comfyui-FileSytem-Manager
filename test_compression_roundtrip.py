#!/usr/bin/env python3
"""
Test for compression/decompression round-trip functionality.
This test verifies that our decompression logic works correctly by:
1. Creating a test file with known content
2. Compressing it to .tar.zst format (using both .tar.zstd and .tar.zst extensions)
3. Decompressing it using our logic
4. Verifying the content matches the original
"""

import os
import sys
import tempfile
import hashlib
import subprocess
import tarfile
from pathlib import Path

# Add the current directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from global_models_manager import GlobalModelsManager
    print("✅ Successfully imported GlobalModelsManager")
except ImportError as e:
    print(f"❌ Failed to import GlobalModelsManager: {e}")
    sys.exit(1)

def create_test_file(content, file_path):
    """Create a test file with specified content"""
    with open(file_path, 'w') as f:
        f.write(content)
    return file_path

def get_file_hash(file_path):
    """Get SHA256 hash of file content"""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def compress_file_to_tar_zst(source_file, output_file, use_zstd_extension=False):
    """Compress a file to .tar.zst format using command line tools"""
    try:
        source_path = Path(source_file)
        output_path = Path(output_file)
        
        # Create tar archive and compress with zstd in one pipeline
        # This mirrors the bash command: tar -cf - file | zstd -o output.tar.zst
        
        # First create a tar archive
        tar_cmd = ['tar', '-cf', '-', '-C', str(source_path.parent), source_path.name]
        zstd_cmd = ['zstd', '-o', str(output_path)]
        
        # Run tar piped to zstd
        tar_process = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        zstd_process = subprocess.Popen(zstd_cmd, stdin=tar_process.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Close tar stdout in parent to avoid broken pipe
        tar_process.stdout.close()
        
        # Wait for both processes
        zstd_output, zstd_error = zstd_process.communicate()
        tar_process.wait()
        
        if tar_process.returncode != 0:
            tar_stderr = tar_process.stderr.read().decode() if tar_process.stderr else "Unknown error"
            print(f"❌ tar failed: {tar_stderr}")
            return False
            
        if zstd_process.returncode != 0:
            zstd_stderr = zstd_error.decode() if zstd_error else "Unknown error"
            print(f"❌ zstd compression failed: {zstd_stderr}")
            return False
        
        print(f"✅ Compressed {source_file} to {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Compression failed: {e}")
        return False

async def test_compression_roundtrip():
    """Test complete compression/decompression round-trip"""
    print("🚀 Starting compression round-trip test...")
    
    # Create temporary directory for our test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test content - something substantial to compress
        test_content = """# Test Model File
This is a test model file used for compression testing.
It contains multiple lines of text to ensure we have something meaningful to compress.

Model parameters:
- Learning rate: 0.001
- Batch size: 32
- Epochs: 100
- Architecture: Transformer
- Hidden dimensions: 512
- Attention heads: 8

Training data:
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor 
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis 
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore
eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident,
sunt in culpa qui officia deserunt mollit anim id est laborum.

This content is repeated several times to make compression worthwhile.
""" * 10  # Repeat 10 times to make it substantial
        
        # Test files
        original_file = temp_path / "test_model.bin"
        compressed_file_zst = temp_path / "test_model.bin.tar.zst"
        compressed_file_zstd = temp_path / "test_model.bin.tar.zstd"
        decompressed_file_zst = temp_path / "decompressed_zst.bin"
        decompressed_file_zstd = temp_path / "decompressed_zstd.bin"
        
        print(f"📁 Test directory: {temp_dir}")
        
        # Step 1: Create original test file
        print("📝 Creating original test file...")
        create_test_file(test_content, original_file)
        original_size = original_file.stat().st_size
        original_hash = get_file_hash(original_file)
        print(f"✅ Original file: {original_file.name} ({original_size} bytes)")
        print(f"🔑 Original hash: {original_hash}")
        
        # Step 2: Compress to both .tar.zst and .tar.zstd formats
        print("\n🗜️ Compressing to .tar.zst format...")
        success_zst = compress_file_to_tar_zst(original_file, compressed_file_zst)
        
        print("🗜️ Compressing to .tar.zstd format...")
        success_zstd = compress_file_to_tar_zst(original_file, compressed_file_zstd)
        
        if not success_zst or not success_zstd:
            print("❌ Compression failed")
            return False
        
        # Check compressed file sizes
        compressed_size_zst = compressed_file_zst.stat().st_size
        compressed_size_zstd = compressed_file_zstd.stat().st_size
        compression_ratio_zst = (1 - compressed_size_zst / original_size) * 100
        compression_ratio_zstd = (1 - compressed_size_zstd / original_size) * 100
        
        print(f"✅ Compressed .tar.zst: {compressed_size_zst} bytes ({compression_ratio_zst:.1f}% reduction)")
        print(f"✅ Compressed .tar.zstd: {compressed_size_zstd} bytes ({compression_ratio_zstd:.1f}% reduction)")
        
        # Step 3: Initialize GlobalModelsManager and test decompression
        print("\n🔄 Testing decompression with GlobalModelsManager...")
        manager = GlobalModelsManager()
        
        # Test .tar.zst decompression
        print("🔄 Testing .tar.zst decompression...")
        # Create separate temp dir for first test
        zst_temp_dir = temp_path / "zst_test"
        zst_temp_dir.mkdir()
        zst_temp_output = zst_temp_dir / "decompressed_zst.bin"
        success_decompress_zst = await manager._decompress_file(
            str(compressed_file_zst), str(zst_temp_output)
        )
        # Move result to final location
        if success_decompress_zst and zst_temp_output.exists():
            zst_temp_output.rename(decompressed_file_zst)
        
        # Test .tar.zstd decompression
        print("🔄 Testing .tar.zstd decompression...")
        # Create separate temp dir for second test
        zstd_temp_dir = temp_path / "zstd_test"
        zstd_temp_dir.mkdir()
        zstd_temp_output = zstd_temp_dir / "decompressed_zstd.bin"
        success_decompress_zstd = await manager._decompress_file(
            str(compressed_file_zstd), str(zstd_temp_output)
        )
        # Move result to final location
        if success_decompress_zstd and zstd_temp_output.exists():
            zstd_temp_output.rename(decompressed_file_zstd)
        
        if not success_decompress_zst or not success_decompress_zstd:
            print("❌ Decompression failed")
            return False
        
        # Step 4: Verify decompressed files
        print("\n🔍 Verifying decompressed files...")
        
        # Check .tar.zst decompression
        if not decompressed_file_zst.exists():
            print("❌ Decompressed .tar.zst file does not exist")
            return False
        
        decompressed_size_zst = decompressed_file_zst.stat().st_size
        decompressed_hash_zst = get_file_hash(decompressed_file_zst)
        
        print(f"📄 Decompressed .tar.zst: {decompressed_size_zst} bytes")
        print(f"🔑 Decompressed .tar.zst hash: {decompressed_hash_zst}")
        
        # Check .tar.zstd decompression
        if not decompressed_file_zstd.exists():
            print("❌ Decompressed .tar.zstd file does not exist")
            return False
            
        decompressed_size_zstd = decompressed_file_zstd.stat().st_size
        decompressed_hash_zstd = get_file_hash(decompressed_file_zstd)
        
        print(f"📄 Decompressed .tar.zstd: {decompressed_size_zstd} bytes")
        print(f"🔑 Decompressed .tar.zstd hash: {decompressed_hash_zstd}")
        
        # Step 5: Verify round-trip integrity
        print("\n✅ Verifying round-trip integrity...")
        
        success = True
        
        # Check sizes
        if original_size != decompressed_size_zst:
            print(f"❌ Size mismatch for .tar.zst: {original_size} != {decompressed_size_zst}")
            success = False
        else:
            print("✅ .tar.zst size matches original")
            
        if original_size != decompressed_size_zstd:
            print(f"❌ Size mismatch for .tar.zstd: {original_size} != {decompressed_size_zstd}")
            success = False
        else:
            print("✅ .tar.zstd size matches original")
        
        # Check hashes
        if original_hash != decompressed_hash_zst:
            print(f"❌ Hash mismatch for .tar.zst:")
            print(f"   Original:     {original_hash}")
            print(f"   Decompressed: {decompressed_hash_zst}")
            success = False
        else:
            print("✅ .tar.zst hash matches original")
            
        if original_hash != decompressed_hash_zstd:
            print(f"❌ Hash mismatch for .tar.zstd:")
            print(f"   Original:     {original_hash}")
            print(f"   Decompressed: {decompressed_hash_zstd}")
            success = False
        else:
            print("✅ .tar.zstd hash matches original")
        
        # Step 6: Test content comparison
        print("\n📖 Comparing file contents...")
        
        with open(original_file, 'r') as f:
            original_content = f.read()
            
        with open(decompressed_file_zst, 'r') as f:
            decompressed_content_zst = f.read()
            
        with open(decompressed_file_zstd, 'r') as f:
            decompressed_content_zstd = f.read()
        
        if original_content == decompressed_content_zst:
            print("✅ .tar.zst content matches original")
        else:
            print("❌ .tar.zst content differs from original")
            success = False
            
        if original_content == decompressed_content_zstd:
            print("✅ .tar.zstd content matches original")
        else:
            print("❌ .tar.zstd content differs from original")
            success = False
        
        return success

def check_dependencies():
    """Check if required dependencies are available"""
    print("🔍 Checking dependencies...")
    
    try:
        # Check for zstd command
        result = subprocess.run(['zstd', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            print(f"✅ zstd available: {version}")
        else:
            print("❌ zstd command not available")
            return False
    except FileNotFoundError:
        print("❌ zstd command not found in PATH")
        return False
    
    try:
        # Check for tar command
        result = subprocess.run(['tar', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ tar command available")
        else:
            print("❌ tar command not available")
            return False
    except FileNotFoundError:
        print("❌ tar command not found in PATH")
        return False
    
    return True

async def main():
    """Main test function"""
    print("🧪 Compression Round-trip Test")
    print("=" * 50)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n❌ Missing required dependencies. Please install zstd:")
        print("  macOS: brew install zstd")
        print("  Ubuntu/Debian: sudo apt-get install zstd")
        print("  CentOS/RHEL: sudo yum install zstd")
        return False
    
    print()
    
    try:
        success = await test_compression_roundtrip()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 All tests passed! Compression round-trip works correctly.")
            print("✅ Both .tar.zst and .tar.zstd formats are supported")
            print("✅ Decompression logic preserves file integrity")
            return True
        else:
            print("❌ Some tests failed. Check the output above for details.")
            return False
            
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import asyncio
    
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
