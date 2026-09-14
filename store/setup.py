from setuptools import find_packages, setup

setup(
    name="financial-data-store",
    version="0.1.0",
    description="Financial file inventory as a backend of a data-lake host",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={"datalake.backends": ["financial_files=financial_data_store.provider:backend"]},
    install_requires=["pandas>=2.0", "pyarrow>=14.0"],
    python_requires=">=3.10",
)
