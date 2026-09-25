#!/usr/bin/python3
"""Convert the field-tuning YAML into one ROS launch argument per line."""
import argparse
from pathlib import Path

import yaml


ALLOWED = {
    'confidence_threshold', 'red_color', 'model_input_width', 'model_input_height',
    'inference_threads', 'publish_annotated_image',
    'lidar_voxel_before_ground', 'lidar_voxel_leaf_size',
    'lidar_ransac_distance_threshold', 'lidar_ground_max_tilt_deg',
    'lidar_ransac_max_iterations', 'lidar_ransac_probability',
    'lidar_cluster_tolerance', 'lidar_min_cluster_size', 'lidar_max_cluster_size',
    'lidar_max_cone_width', 'lidar_min_cone_height', 'lidar_max_cone_height',
    'lidar_max_detection_range', 'profile_lidar',
    'fusion_wait_sec', 'fusion_sync_slop_sec', 'fusion_max_match_distance',
    'fusion_mahalanobis_gate', 'fusion_pixel_margin', 'fusion_ambiguity_margin',
    'fusion_min_color_probability', 'fusion_fuse_positions',
    'publish_unmatched_lidar', 'guided_voxel_size', 'guided_cluster_tolerance',
    'guided_depth_tolerance', 'guided_min_cluster_size', 'guided_max_cluster_size',
    'guided_max_width', 'guided_min_height', 'guided_max_height', 'debug_orange',
    'debug_sync_slop_sec', 'debug_pixel_margin',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        parser.error('field tuning YAML must be a mapping')
    unknown = set(data) - ALLOWED
    if unknown:
        parser.error('unknown field tuning keys: ' + ', '.join(sorted(unknown)))
    for name, value in data.items():
        if isinstance(value, bool):
            value = str(value).lower()
        elif not isinstance(value, (int, float)):
            parser.error(f'{name} must be a number or boolean')
        print(f'{name}:={value}')


if __name__ == '__main__':
    main()
