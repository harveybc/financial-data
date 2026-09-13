from setuptools import find_packages, setup

setup(
    name="financial-lake",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"web_plugins": ["templates/*.html", "static/css/*.css"]},
    entry_points={
        "console_scripts": ["financial-lake=app.main:main"],
        "finlake.pipeline": [
            "default_pipeline=pipeline_plugins.default_pipeline:Plugin",
        ],
        "finlake.web": ["default_web=web_plugins.default_web:Plugin"],
        "finlake.inventory": [
            "fs_inventory=inventory_plugins.fs_inventory:Plugin",
        ],
    },
    install_requires=["flask>=3.0", "pandas>=2.0", "pyarrow>=14.0"],
)
