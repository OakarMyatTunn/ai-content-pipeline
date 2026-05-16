"""
Animal Module — Step 2.
Generates frames using local DreamShaper 8 (SD 1.5 fine-tune).
Optimised for RTX 3050 4GB VRAM.
DreamShaper 8 produces much better cartoon/artistic animal style
vs vanilla SD 1.5, while using identical VRAM and pipeline class.
"""
import gc
import torch
from pathlib import Path
from PIL import Image
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
from modules.shared.config_loader import cfg
from modules.shared.logger import log


_pipe = None  # lazy-loaded, kept in memory between daily runs


def _load_pipeline() -> StableDiffusionPipeline:
    global _pipe
    if _pipe is not None:
        return _pipe

    log.info(f"Loading SD pipeline: {cfg.SD_MODEL}")
    log.info(f"Device: {cfg.SD_DEVICE} | Low VRAM: {cfg.SD_LOW_VRAM}")

    # DreamShaper 8 supports fp16 variant — faster load, less RAM
    try:
        _pipe = StableDiffusionPipeline.from_pretrained(
            cfg.SD_MODEL,
            torch_dtype=torch.float16 if cfg.SD_DEVICE == "cuda" else torch.float32,
            variant="fp16",
            safety_checker=None,
            requires_safety_checker=False,
        )
        log.info("Loaded with fp16 variant")
    except Exception:
        # Fallback: load without variant (works for any SD 1.5 model)
        log.info("fp16 variant not found, loading default weights...")
        _pipe = StableDiffusionPipeline.from_pretrained(
            cfg.SD_MODEL,
            torch_dtype=torch.float16 if cfg.SD_DEVICE == "cuda" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False,
        )

    # DPM++ 2M Karras — best quality/speed for cartoon style at 35 steps
    _pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        _pipe.scheduler.config,
        use_karras_sigmas=True,
        algorithm_type="dpmsolver++",   # required when use_karras_sigmas=True
    )

    if cfg.SD_DEVICE == "cuda":
        if cfg.SD_LOW_VRAM:
            _pipe.enable_model_cpu_offload()
            log.info("CPU offload enabled (low VRAM mode)")
        else:
            _pipe = _pipe.to("cuda")
            _pipe.enable_attention_slicing()
            log.info("Attention slicing enabled for 4GB VRAM")
    else:
        _pipe = _pipe.to("cpu")
        log.warning("Running on CPU — generation will be slow")

    log.info("SD pipeline loaded ✓")
    return _pipe


def generate_frames(concept: dict, out_dir: Path, n_frames: int = None) -> list[Path]:
    """
    Generate N frames from concept's SD prompt.
    Returns list of saved image paths.
    """
    n = n_frames or cfg.SD_FRAMES
    prompt   = concept["sd_prompt"]
    negative = concept["sd_negative"]
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Generating {n} frames | style: {concept.get('style','?')}")
    log.info(f"Prompt: {prompt[:100]}...")

    pipe = _load_pipeline()
    paths = []

    for i in range(n):
        log.info(f"  Frame {i+1}/{n}...")
        with torch.inference_mode():
            result = pipe(
                prompt=prompt,
                negative_prompt=negative,
                width=cfg.SD_WIDTH,
                height=cfg.SD_HEIGHT,
                num_inference_steps=cfg.SD_STEPS,
                guidance_scale=cfg.SD_GUIDANCE,
                # Varied seeds for frame diversity
                generator=torch.Generator(device=cfg.SD_DEVICE).manual_seed(i * 137 + 42),
            )
        img: Image.Image = result.images[0]
        frame_path = out_dir / f"frame_{i:04d}.png"
        img.save(frame_path)
        paths.append(frame_path)

    log.info(f"Generated {len(paths)} frames ✓")

    if cfg.SD_DEVICE == "cuda":
        torch.cuda.empty_cache()
        gc.collect()

    return paths


def unload_pipeline() -> None:
    """Free GPU memory when not in use."""
    global _pipe
    if _pipe is not None:
        del _pipe
        _pipe = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        log.info("SD pipeline unloaded from GPU")
