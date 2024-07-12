import setuptools
from glob import glob


setuptools.setup(
    name="nbpilot",
    version="0.0.1",
    author="Rossi",
    description="A copilot which works collectively with you in a notebook.",
    packages=setuptools.find_packages(".", exclude=["test"]),
    data_files=[("config", glob("config/*"))],
    classifiers=[
        "Framework :: Jupyter",
    ],
    include_package_data=True,
    zip_safe=False,
    entry_points = {  
        'console_scripts': [  
             'nbpilot = nbpilot.__main__:main'  
         ]  
    }
)
