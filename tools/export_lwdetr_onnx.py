#!/usr/bin/env python3
"""Export the supplied LW-DETR checkpoint to a fixed 1280x768 ONNX graph."""
import argparse
import sys
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'WUTA-FSD/ros2_ws/src/perception/camera_detection/models'
DEPS = ROOT / '.hardware_deps'
LWDETR = DEPS / 'LW-DETR'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint', type=Path,
                        default=MODEL_DIR / 'checkpoint_best_ema.pth.1')
    parser.add_argument('--output', type=Path, default=MODEL_DIR / 'lwdetr-fp16.onnx')
    parser.add_argument('--height', type=int, default=768)
    parser.add_argument('--width', type=int, default=1280)
    args = parser.parse_args()
    sys.path[:0] = [str(LWDETR), str(DEPS)]

    import argparse as argparse_module
    torch.serialization.add_safe_globals([argparse_module.Namespace])
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model_args = checkpoint['args']
    model_args.device = 'cpu'
    from models import build_model

    model, _, _ = build_model(model_args)
    model.load_state_dict(checkpoint['model'], strict=True)
    model.eval().cpu().export()
    # LW-DETR's upstream export() precomputes the ViT absolute position table
    # for 640x640. The supplied checkpoint was trained for 1280x768, so
    # interpolate that table to this fixed patch grid before tracing.
    from models.backbone.vit import get_abs_pos
    for module in model.modules():
        if hasattr(module, 'pos_embed') and hasattr(module, 'pos_embed_export'):
            patch = module.patch_embed.proj.kernel_size
            grid = (args.height // patch[0], args.width // patch[1])
            module.pos_embed_export = get_abs_pos(
                module.pos_embed, module.pretrain_use_cls_token, grid).detach()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sample = torch.zeros((1, 3, args.height, args.width), dtype=torch.float32)
    with torch.inference_mode():
        coords, logits = model(sample)
    print(f'PyTorch reference shapes: boxes={tuple(coords.shape)}, logits={tuple(logits.shape)}')
    torch.onnx.export(
        model, sample, str(args.output), input_names=['input'],
        output_names=['dets', 'labels'], opset_version=17,
        do_constant_folding=True, keep_initializers_as_inputs=False,
        dynamo=False)
    print(f'Wrote {args.output} ({args.width}x{args.height})')


if __name__ == '__main__':
    main()
