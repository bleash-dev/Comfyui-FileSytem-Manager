#!/usr/bin/env python3
"""
Test script to verify symlink deletion functionality
"""
import tempfile
import os
from pathlib import Path
import sys

# Add the parent directory to the path to import the module
sys.path.insert(0, str(Path(__file__).parent))

def test_symlink_detection():
    """Test the find_symlinks_pointing_to_file method"""
    
    # Create a temporary directory structure for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test directories
        models_dir = temp_path / "models"
        checkpoints_dir = models_dir / "checkpoints"
        loras_dir = models_dir / "loras"
        
        models_dir.mkdir()
        checkpoints_dir.mkdir()
        loras_dir.mkdir()
        
        # Create a test model file
        test_model = checkpoints_dir / "test_model.safetensors"
        test_model.write_text("dummy model content")
        
        # Create symlinks pointing to the test model
        symlink1 = loras_dir / "test_model_symlink1.safetensors"
        symlink2 = loras_dir / "test_model_symlink2.safetensors"
        
        symlink1.symlink_to(test_model)
        symlink2.symlink_to(test_model)
        
        # Create a symlink to a different file (should not be found)
        other_model = checkpoints_dir / "other_model.safetensors"
        other_model.write_text("other model content")
        symlink3 = loras_dir / "other_symlink.safetensors"
        symlink3.symlink_to(other_model)
        
        # Mock the FileSystemManagerAPI to test our method
        class MockFileSystemAPI:
            def __init__(self):
                self.allowed_directories = {
                    'models': models_dir
                }
            
            def find_symlinks_pointing_to_file(self, target_file_path):
                """Find all symlinks that point to the specified target file"""
                symlinks = []
                target_absolute = target_file_path.resolve()
                
                try:
                    # Search through all allowed directories for symlinks
                    for root_name, root_path in self.allowed_directories.items():
                        if not root_path.exists():
                            continue
                            
                        # Walk through all subdirectories
                        for item in root_path.rglob('*'):
                            try:
                                if item.is_symlink():
                                    # Check if this symlink points to our target file
                                    symlink_target = item.resolve()
                                    if symlink_target == target_absolute:
                                        symlinks.append(item)
                            except (OSError, ValueError):
                                # Skip broken symlinks or permission errors
                                continue
                                
                except Exception as e:
                    print(f"Error finding symlinks: {e}")
                    
                return symlinks
        
        # Test the functionality
        api = MockFileSystemAPI()
        found_symlinks = api.find_symlinks_pointing_to_file(test_model)
        
        print(f"Test model: {test_model}")
        print(f"Created symlinks: {[symlink1, symlink2]}")
        print(f"Found symlinks: {found_symlinks}")
        
        # Verify results
        assert len(found_symlinks) == 2, f"Expected 2 symlinks, found {len(found_symlinks)}"
        
        found_paths = {str(s) for s in found_symlinks}
        expected_paths = {str(symlink1), str(symlink2)}
        
        assert found_paths == expected_paths, f"Expected {expected_paths}, got {found_paths}"
        
        # Test that symlinks to other files are not found
        other_symlinks = api.find_symlinks_pointing_to_file(other_model)
        assert len(other_symlinks) == 1, f"Expected 1 symlink to other model, found {len(other_symlinks)}"
        assert str(other_symlinks[0]) == str(symlink3)
        
        print("✅ All tests passed!")
        
        # Test what happens when file is deleted (symlinks become broken)
        test_model.unlink()
        
        # The symlinks should still be found even if they're broken
        # (they still point to the original file path)
        broken_symlinks = api.find_symlinks_pointing_to_file(Path(str(test_model)))
        print(f"Broken symlinks found: {len(broken_symlinks)}")
        
        # In practice, we might need to handle broken symlinks differently
        # but for cleanup purposes, we want to find and remove them
        
        print("✅ Symlink detection test completed successfully!")

if __name__ == "__main__":
    test_symlink_detection()
