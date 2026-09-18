"""Dedicated late-fusion simulation; normal driving, sensor-derived cone map."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('simulator_bringup')
    return LaunchDescription([
        DeclareLaunchArgument('track_file', default_value='trackdrive'),
        DeclareLaunchArgument('mission_mode', default_value='trackdrive'),
        DeclareLaunchArgument('launch_rviz', default_value='true'),
        DeclareLaunchArgument('rviz_config', default_value=PathJoinSubstitution([
            share, 'rviz', 'fusion_simulator.rviz'])),
        DeclareLaunchArgument('simulate_camera', default_value='true', choices=['true', 'false']),
        DeclareLaunchArgument('use_ground_truth_localization', default_value='false'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution([share, 'launch', 'simulator.launch.py'])),
            launch_arguments={
                'track_file': LaunchConfiguration('track_file'),
                'mission_mode': LaunchConfiguration('mission_mode'),
                'launch_rviz': LaunchConfiguration('launch_rviz'),
                'rviz_config': LaunchConfiguration('rviz_config'),
                'use_detection_fusion': 'true', 'use_track_truth_map': 'false',
                'use_simulated_cone_colors': 'false', 'launch_fsd': 'true',
                'use_ground_truth_localization': LaunchConfiguration('use_ground_truth_localization'),
            }.items()),
        Node(package='simulator_bringup', executable='simulated_stereo_detections',
             parameters=[{'track_file': LaunchConfiguration('track_file')}], output='screen',
             condition=IfCondition(LaunchConfiguration('simulate_camera'))),
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='sim_camera_extrinsics', arguments=[
                 '--x', '0', '--y', '0', '--z', '0.5',
                 '--qx', '-0.5', '--qy', '0.5', '--qz', '-0.5', '--qw', '0.5',
                 '--frame-id', 'base_link', '--child-frame-id', 'sim_camera_left_optical_frame']),
    ])
