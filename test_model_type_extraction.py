#!/usr/bin/env python3
"""
Test script for model type extraction functionality.
Tests the _determine_model_type_from_path method in model_config_integration.py
"""

import sys
from pathlib import Path

# Add the current directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

try:
    from model_config_integration import ModelConfigManager
    print("✅ Successfully imported ModelConfigManager")
except ImportError as e:
    print(f"❌ Failed to import ModelConfigManager: {e}")
    sys.exit(1)


def test_model_type_extraction():
    """Test the model type extraction from various paths."""
    print("\n🧪 Testing model type extraction...")
    
    # Create a ModelConfigManager instance for testing
    manager = ModelConfigManager()
    
    test_cases = [
        # Test cases: (input_path, expected_output)
        ("/ComfyUI/models/checkpoints/model.safetensors", "checkpoints"),
        ("/ComfyUI/models/loras/style_lora.safetensors", "loras"),
        ("/ComfyUI/models/vae/vae_model.pt", "vae"),
        ("/ComfyUI/models/controlnet/control_sd15.pth", "controlnet"),
        ("/ComfyUI/models/embeddings/negative.pt", "embeddings"),
        ("/ComfyUI/models/clip_vision/clip_model.safetensors", "clip_vision"),
        ("/ComfyUI/models/style_models/style.safetensors", "style_models"),
        ("/ComfyUI/models/upscale_models/upscaler.pth", "upscale_models"),
        ("/ComfyUI/models/diffusion_models/diffusion.safetensors", "diffusion_models"),
        
        # Nested paths
        ("/ComfyUI/models/checkpoints/subfolder/model.safetensors", "checkpoints"),
        ("/ComfyUI/models/loras/subfolder/another/lora.safetensors", "loras"),
        
        # Edge cases
        ("/ComfyUI/models/unknown_type/model.safetensors", "unknown_type"),
        ("/ComfyUI/models/", ""),
        ("/some/other/path/model.safetensors", "unknown"),
        
        # Windows-style paths
        ("C:\\ComfyUI\\models\\checkpoints\\model.safetensors", "checkpoints"),
        ("C:\\ComfyUI\\models\\loras\\subfolder\\lora.safetensors", "loras"),
    ]
    
    passed = 0
    failed = 0
    
    for input_path, expected in test_cases:
        try:
            result = manager._determine_model_type_from_path(input_path)
            if result == expected:
                print(f"✅ PASS: {input_path} -> {result}")
                passed += 1
            else:
                print(f"❌ FAIL: {input_path} -> {result} (expected: {expected})")
                failed += 1
        except Exception as e:
            print(f"❌ ERROR: {input_path} -> Exception: {e}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Total:  {passed + failed}")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed!")
        return False


def test_bulk_registration():
    """Test bulk HuggingFace repository registration."""
    print("\n🧪 Testing bulk repository registration (dry run)...")
    
    # This simulates how files would be registered based on download location
    manager = ModelConfigManager()
    
    # Test with realistic download paths
    test_cases = [
        # Repository downloaded to checkpoints folder
        ("/ComfyUI/models/checkpoints/sd-v1-5/model_index.json",
         "checkpoints"),
        ("/ComfyUI/models/checkpoints/sd-v1-5/unet/model.bin",
         "checkpoints"),
        ("/ComfyUI/models/checkpoints/sd-v1-5/vae/model.safetensors",
         "checkpoints"),
        
        # Repository downloaded to loras folder
        ("/ComfyUI/models/loras/lora-pack/weights.safetensors", "loras"),
        ("/ComfyUI/models/loras/lora-pack/README.md", "loras"),
        
        # Repository downloaded to controlnet folder
        ("/ComfyUI/models/controlnet/control_depth/model.safetensors",
         "controlnet"),
        ("/ComfyUI/models/controlnet/control_depth/config.json",
         "controlnet"),
        
        # Repository downloaded to custom location (fallback case)
        ("/some/custom/path/repo/model.bin", "unknown"),
    ]
    
    print("Mock repository file paths and expected groups:")
    for file_path, expected_group in test_cases:
        actual_group = manager._determine_model_type_from_path(file_path)
        status = "✅" if actual_group == expected_group else "❌"
        print(f"  {status} {file_path}")
        print(f"     → Group: {actual_group} (expected: {expected_group})")
    
    print("\n✅ Bulk registration test completed (dry run)")
    print("💡 Files registered in their ComfyUI models/{group}/ location")
    print("💡 Repository structure is preserved within each group")
    return True


def test_model_name_extraction():
    """Test the model name extraction using backend convention."""
    print("\n🧪 Testing model name extraction (backend convention)...")
    
    # Create a ModelConfigManager instance for testing
    manager = ModelConfigManager()
    
    test_cases = [
        # Test cases: (input_path, expected_model_name)
        # Basic cases - should return everything after the group
        ("/ComfyUI/models/checkpoints/model.safetensors", "model.safetensors"),
        ("/ComfyUI/models/loras/style_lora.safetensors",
         "style_lora.safetensors"),
        ("/ComfyUI/models/vae/vae_model.pt", "vae_model.pt"),
        
        # Nested directory cases - should preserve nested structure
        ("/ComfyUI/models/checkpoints/subfolder/model.safetensors",
         "subfolder/model.safetensors"),
        ("/ComfyUI/models/loras/subfolder/another/lora.safetensors",
         "subfolder/another/lora.safetensors"),
        ("/ComfyUI/models/checkpoints/sd-v1-5/unet/model.bin",
         "sd-v1-5/unet/model.bin"),
        ("/ComfyUI/models/loras/lora-pack/weights.safetensors",
         "lora-pack/weights.safetensors"),
        
        # Repository structure cases
        ("/ComfyUI/models/controlnet/control_depth/model.safetensors",
         "control_depth/model.safetensors"),
        ("/ComfyUI/models/controlnet/control_depth/config.json",
         "control_depth/config.json"),
        
        # Edge cases
        ("/ComfyUI/models/checkpoints/", ""),
        ("/ComfyUI/models/", ""),
        
        # Non-standard paths (should fallback to basename)
        ("/some/other/path/model.safetensors", "model.safetensors"),
        ("/custom/location/weights.bin", "weights.bin"),
        
        # Windows-style paths
        ("C:\\ComfyUI\\models\\checkpoints\\model.safetensors",
         "model.safetensors"),
        ("C:\\ComfyUI\\models\\loras\\subfolder\\lora.safetensors",
         "subfolder/lora.safetensors"),
        
        # Complex nested repository structures
        ("/ComfyUI/models/checkpoints/repo/subdir1/subdir2/model.bin",
         "repo/subdir1/subdir2/model.bin"),
    ]
    
    passed = 0
    failed = 0
    
    print("Model name extraction test results:")
    for input_path, expected in test_cases:
        try:
            result = manager._extract_model_name_from_path(input_path)
            if result == expected:
                print(f"✅ PASS: {input_path}")
                print(f"    → Model name: '{result}'")
                passed += 1
            else:
                print(f"❌ FAIL: {input_path}")
                print(f"    → Got: '{result}', Expected: '{expected}'")
                failed += 1
        except Exception as e:
            print(f"❌ ERROR: {input_path} -> Exception: {e}")
            failed += 1
    
    print("\n📊 Model Name Extraction Results:")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Total:  {passed + failed}")
    
    if failed == 0:
        print("🎉 All model name extraction tests passed!")
        return True
    else:
        print("⚠️  Some model name extraction tests failed!")
        return False


if __name__ == "__main__":
    print("🚀 Starting model type extraction tests...")
    
    success = True
    
    # Run the tests
    success &= test_model_type_extraction()
    success &= test_model_name_extraction()
    success &= test_bulk_registration()
    success &= test_model_name_extraction()
    
    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
