import os

# This mapping directly connects the Python class name of a ComfyUI loader node
# to the filesystem directory (or directories) it loads models or data from.
# It is designed to be comprehensive based on the provided nodes.py code.
LOADER_CLASS_TO_DIRECTORY_MAPPING = {
    # --- Checkpoint Loaders (all use the 'checkpoints' directory) ---
    "CheckpointLoaderSimple": "checkpoints",
    "CheckpointLoader": "checkpoints",         # Deprecated but uses the same directory
    "unCLIPCheckpointLoader": "checkpoints",   # For models with CLIP Vision component

    # --- Diffusers Loader ---
    "DiffusersLoader": "diffusers",

    # --- VAE Loader (handles both full and approximate VAEs) ---
    "VAELoader": ("vae", "vae_approx"),        # Can load from both directories

    # --- LoRA Loaders (both use the 'loras' directory) ---
    "LoraLoader": "loras",
    "LoraLoaderModelOnly": "loras",

    # --- ControlNet Loaders (both use the 'controlnet' directory) ---
    "ControlNetLoader": "controlnet",
    "DiffControlNetLoader": "controlnet",

    # --- CLIP / Text Encoder Loaders (both use 'text_encoders') ---
    "CLIPLoader": "text_encoders",
    "DualCLIPLoader": "text_encoders",

    # --- Other Component & Data Loaders ---
    "UNETLoader": "diffusion_models",
    "CLIPVisionLoader": "clip_vision",
    "StyleModelLoader": "style_models",
    "GLIGENLoader": "gligen",
    "LoadImage": "input",
    "LoadImageMask": "input",
    "LoadLatent": "input",

    # --- Common Loader Nodes from comfy_extras ---
    "HypernetworkLoad": "hypernetworks",
    "UpscaleModelLoader": "upscale_models",
    
    # --- Special case for the concept of Textual Inversion embeddings ---
    "TextualInversion": "embeddings",
}

# Automatically create the reverse mapping. This maps a directory to a list of
# loader classes that use it.
DIRECTORY_TO_LOADER_CLASSES_MAPPING = {}
for loader_class, dirs in LOADER_CLASS_TO_DIRECTORY_MAPPING.items():
    # Ensure dirs is a tuple/list to handle single and multiple directories gracefully
    if not isinstance(dirs, (list, tuple)):
        dirs = (dirs,)
    
    for directory in dirs:
        if directory not in DIRECTORY_TO_LOADER_CLASSES_MAPPING:
            DIRECTORY_TO_LOADER_CLASSES_MAPPING[directory] = []
        DIRECTORY_TO_LOADER_CLASSES_MAPPING[directory].append(loader_class)


def get_directories_for_loader_class(loader_class_name: str) -> tuple[str, ...] | None:
    """
    Maps a ComfyUI loader node's class name to its corresponding model/input directory(s).

    Args:
        loader_class_name (str): The exact class name of the loader node
                                 (e.g., "VAELoader", "LoraLoader"). Case-sensitive.

    Returns:
        tuple[str, ...] | None: A tuple of directory names (e.g., ("vae", "vae_approx"))
                                or None if the loader class is not found.
    """
    dirs = LOADER_CLASS_TO_DIRECTORY_MAPPING.get(loader_class_name)
    if dirs is None:
        return None
    if not isinstance(dirs, (list, tuple)):
        return (dirs,)
    return tuple(dirs)

def get_loader_classes_for_directory(directory_name: str) -> list[str] | None:
    """
    Maps a model or input directory name to a list of ComfyUI loader node classes
    that use that directory.

    Args:
        directory_name (str): The name of the directory (e.g., "checkpoints", "vae").
                              The input is case-insensitive.

    Returns:
        list[str] | None: A list of corresponding loader class names
                          or None if the directory is not found.
    """
    return DIRECTORY_TO_LOADER_CLASSES_MAPPING.get(directory_name.lower())

