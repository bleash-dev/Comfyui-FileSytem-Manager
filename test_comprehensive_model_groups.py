#!/usr/bin/env python3
"""
Test script to verify the comprehensive _determine_model_group method
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from model_config_integration import ModelConfigManager


def test_comprehensive_model_groups():
    """Test the updated _determine_model_group method with comprehensive model types"""
    manager = ModelConfigManager()
    
    # Test cases: (path, expected_group)
    test_cases = [
        # Core ComfyUI model types
        ("/ComfyUI/models/checkpoints/sd15.safetensors", "checkpoints"),
        ("/ComfyUI/models/diffusion_models/unet.safetensors", "diffusion_models"),
        ("/ComfyUI/models/unet/model.safetensors", "diffusion_models"),
        ("/ComfyUI/models/vae/vae.safetensors", "vae"),
        ("/ComfyUI/models/vae_approx/taesd_decoder.pth", "vae_approx"),
        ("/ComfyUI/models/text_encoders/clip-l.safetensors", "text_encoders"),
        ("/ComfyUI/models/clip/clip-g.safetensors", "text_encoders"),
        ("/ComfyUI/models/clip_vision/clip_vision.safetensors", "clip_vision"),
        ("/ComfyUI/models/loras/style.safetensors", "loras"),
        ("/ComfyUI/models/controlnet/canny.safetensors", "controlnet"),
        ("/ComfyUI/models/t2i_adapter/adapter.safetensors", "controlnet"),
        ("/ComfyUI/models/embeddings/embedding.pt", "embeddings"),
        ("/ComfyUI/models/upscale_models/4x_esrgan.pth", "upscale_models"),
        ("/ComfyUI/models/style_models/style.safetensors", "style_models"),
        ("/ComfyUI/models/gligen/gligen.safetensors", "gligen"),
        ("/ComfyUI/models/hypernetworks/hyper.pt", "hypernetworks"),
        ("/ComfyUI/models/photomaker/photomaker.bin", "photomaker"),
        ("/ComfyUI/models/classifiers/classifier.pth", "classifiers"),
        ("/ComfyUI/models/diffusers/stable-diffusion", "diffusers"),
        
        # Custom node model types
        ("/ComfyUI/models/ipadapter/ip_adapter.safetensors", "ipadapter"),
        ("/ComfyUI/models/ip_adapter/adapter.safetensors", "ipadapter"),
        ("/ComfyUI/models/ip-adapter/model.safetensors", "ipadapter"),
        ("/ComfyUI/models/animatediff/motion_module.safetensors", "animatediff"),
        ("/ComfyUI/models/motion_module/mm.safetensors", "animatediff"),
        ("/ComfyUI/models/motion-module/module.safetensors", "animatediff"),
        ("/ComfyUI/models/insightface/face_model.onnx", "insightface"),
        ("/ComfyUI/models/face_analysis/model.onnx", "insightface"),
        ("/ComfyUI/models/instantid/instant_id.safetensors", "instantid"),
        ("/ComfyUI/models/instant_id/model.safetensors", "instantid"),
        ("/ComfyUI/models/inpaint/inpaint_model.safetensors", "inpaint"),
        ("/ComfyUI/models/segmentation/sam.pth", "segmentation"),
        ("/ComfyUI/models/segment/model.pth", "segmentation"),
        ("/ComfyUI/models/depth/depth_model.pth", "depth_estimation"),
        ("/ComfyUI/models/depth_estimation/midas.pth", "depth_estimation"),
        ("/ComfyUI/models/pose/openpose.pth", "pose_estimation"),
        ("/ComfyUI/models/pose_estimation/model.pth", "pose_estimation"),
        ("/ComfyUI/models/openpose/pose.pth", "pose_estimation"),
        ("/ComfyUI/models/video/video_model.safetensors", "video_models"),
        ("/ComfyUI/models/video_models/model.safetensors", "video_models"),
        ("/ComfyUI/models/audio/audio_model.safetensors", "audio_models"),
        ("/ComfyUI/models/audio_models/model.safetensors", "audio_models"),
        
        # Unknown types should fall back to 'other'
        ("/ComfyUI/models/unknown_type/model.safetensors", "other"),
        ("/random/path/model.bin", "other"),
    ]
    
    print("Testing comprehensive model group determination...")
    print("=" * 60)
    
    all_passed = True
    
    for i, (path, expected) in enumerate(test_cases):
        # Test path-based detection
        result = manager._determine_model_group(path)
        status = "✓" if result == expected else "✗"
        
        if result != expected:
            all_passed = False
            print(f"{status} FAIL: {path}")
            print(f"    Expected: {expected}, Got: {result}")
        else:
            print(f"{status} PASS: {path} -> {result}")
    
    # Test model_type parameter override
    print("\nTesting model_type parameter override...")
    print("-" * 40)
    
    # Test checkpoint override
    result = manager._determine_model_group("/some/random/path/model.safetensors", model_type="checkpoint")
    expected = "checkpoints"
    status = "✓" if result == expected else "✗"
    if result != expected:
        all_passed = False
        print(f"{status} FAIL: Override with model_type='checkpoint'")
        print(f"    Expected: {expected}, Got: {result}")
    else:
        print(f"{status} PASS: Override with model_type='checkpoint' -> {result}")
    
    # Test lora override
    result = manager._determine_model_group("/another/path/model.pth", model_type="lora")
    expected = "loras"
    status = "✓" if result == expected else "✗"
    if result != expected:
        all_passed = False
        print(f"{status} FAIL: Override with model_type='lora'")
        print(f"    Expected: {expected}, Got: {result}")
    else:
        print(f"{status} PASS: Override with model_type='lora' -> {result}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests PASSED! The comprehensive model group detection is working correctly.")
        return True
    else:
        print("✗ Some tests FAILED! Please check the implementation.")
        return False


def test_model_type_mappings():
    """Test the model_type mappings in the method"""
    manager = ModelConfigManager()
    
    print("\nTesting model_type mappings...")
    print("=" * 40)
    
    # Test cases: (model_type, expected_group)
    mapping_tests = [
        ("checkpoint", "checkpoints"),
        ("diffusion_model", "diffusion_models"),
        ("unet", "diffusion_models"),
        ("vae", "vae"),
        ("vae_approx", "vae_approx"),
        ("text_encoder", "text_encoders"),
        ("clip", "text_encoders"),
        ("clip_vision", "clip_vision"),
        ("lora", "loras"),
        ("controlnet", "controlnet"),
        ("t2i_adapter", "controlnet"),
        ("embedding", "embeddings"),
        ("upscale_model", "upscale_models"),
        ("style_model", "style_models"),
        ("gligen", "gligen"),
        ("hypernetwork", "hypernetworks"),
        ("photomaker", "photomaker"),
        ("classifier", "classifiers"),
        ("diffuser", "diffusers"),
        ("ipadapter", "ipadapter"),
        ("ip_adapter", "ipadapter"),
        ("animatediff", "animatediff"),
        ("motion_module", "animatediff"),
        ("insightface", "insightface"),
        ("face_analysis", "insightface"),
        ("instantid", "instantid"),
        ("inpaint", "inpaint"),
        ("segmentation", "segmentation"),
        ("depth_estimation", "depth_estimation"),
        ("pose_estimation", "pose_estimation"),
        ("video_model", "video_models"),
        ("audio_model", "audio_models"),
    ]
    
    all_passed = True
    
    for model_type, expected in mapping_tests:
        result = manager._determine_model_group("/any/path/model.bin", model_type=model_type)
        status = "✓" if result == expected else "✗"
        
        if result != expected:
            all_passed = False
            print(f"{status} FAIL: model_type='{model_type}'")
            print(f"    Expected: {expected}, Got: {result}")
        else:
            print(f"{status} PASS: model_type='{model_type}' -> {result}")
    
    print("\n" + "=" * 40)
    if all_passed:
        print("✓ All model_type mapping tests PASSED!")
        return True
    else:
        print("✗ Some model_type mapping tests FAILED!")
        return False


if __name__ == "__main__":
    print("Comprehensive Model Group Detection Test")
    print("=" * 60)
    
    try:
        test1_passed = test_comprehensive_model_groups()
        test2_passed = test_model_type_mappings()
        
        print("\n" + "=" * 60)
        print("FINAL RESULTS:")
        print("=" * 60)
        
        if test1_passed and test2_passed:
            print("🎉 ALL TESTS PASSED! The comprehensive model group detection is working perfectly.")
            print("\nThe updated _determine_model_group method now supports:")
            print("• All core ComfyUI model types from folder_paths.py")
            print("• All node types from ComfyUI's nodes.py")
            print("• Common custom node model types")
            print("• Both path-based detection and explicit model_type overrides")
            print("• Proper fallback to 'other' for unknown types")
            sys.exit(0)
        else:
            print("❌ Some tests failed. Please review the implementation.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Test execution failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
