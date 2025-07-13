#!/usr/bin/env python3
"""
Demonstration of centralized model name extraction using backend convention.
Shows how the _extract_model_name_from_path method works across scenarios.
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


def demonstrate_model_name_extraction():
    """Demonstrate the centralized model name extraction."""
    print("\n🎯 Demonstrating Centralized Model Name Extraction")
    print("=" * 60)
    
    manager = ModelConfigManager()
    
    # Examples showing the backend convention
    examples = [
        {
            "description": "Simple model file",
            "path": "/ComfyUI/models/checkpoints/model.safetensors",
            "explanation": "Returns just the filename after the group"
        },
        {
            "description": "Nested repository structure",
            "path": "/ComfyUI/models/checkpoints/sd-v1-5/unet/model.bin",
            "explanation": "Preserves nested structure: repo/subdir/filename"
        },
        {
            "description": "HuggingFace repository file",
            "path": "/ComfyUI/models/loras/lora-pack/weights.safetensors",
            "explanation": "Keeps repository name and filename together"
        },
        {
            "description": "Deep nesting",
            "path": ("/ComfyUI/models/controlnet/control/depth/v1/"
                     "model.safetensors"),
            "explanation": "Preserves entire nested structure after group"
        },
        {
            "description": "Non-standard path (fallback)",
            "path": "/custom/location/model.bin",
            "explanation": "Falls back to basename for non-standard paths"
        }
    ]
    
    for example in examples:
        print(f"\n📁 {example['description']}:")
        print(f"   Path: {example['path']}")
        
        model_name = manager._extract_model_name_from_path(example['path'])
        print(f"   Model Name: '{model_name}'")
        print(f"   💡 {example['explanation']}")
    
    print("\n" + "=" * 60)
    print("🔍 Key Benefits of Centralized Extraction:")
    print("   ✅ Consistent naming across all registration methods")
    print("   ✅ Preserves repository structure for nested downloads")
    print("   ✅ Matches backend engineer's extractModelName convention")
    print("   ✅ Handles edge cases gracefully with fallbacks")
    print("   ✅ Works with both Unix and Windows path formats")


def demonstrate_registration_integration():
    """Show how the extraction integrates with all registration methods."""
    print("\n🔗 Integration with Registration Methods")
    print("=" * 60)
    
    print("All registration methods now use the centralized extraction:")
    print("   • register_s3_model()")
    print("   • register_internet_model()")
    print("   • register_huggingface_model()")
    print("   • register_civitai_model()")
    print("   • register_google_drive_model()")
    print("   • register_direct_url_model()")
    print("   • register_huggingface_repo() (bulk registration)")
    
    print("\n💡 This ensures consistent model naming throughout the system!")


if __name__ == "__main__":
    print("🚀 Model Name Extraction Demonstration")
    
    demonstrate_model_name_extraction()
    demonstrate_registration_integration()
    
    print("\n🎉 Demonstration completed!")
