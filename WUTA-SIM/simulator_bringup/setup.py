from glob import glob

from setuptools import find_packages, setup


package_name = "simulator_bringup"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/rviz", glob("rviz/*.rviz")),
    ],
    install_requires=["setuptools"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="WUTA",
    maintainer_email="wuta@example.com",
    description="Ordered bringup for WUTA simulators and WUTA-FSD.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "simulation_bridge = simulator_bringup.simulation_bridge:main",
            "simulated_cone_colorizer = simulator_bringup.simulated_cone_colorizer:main",
            "track_truth_map_publisher = simulator_bringup.track_truth_map_publisher:main",
        ],
    },
)
