from setuptools import find_packages, setup

with open("README.md") as f:
    readme = f.read()

setup(
    name="turn_rasa_connector",
    version="0.0.1",
    description="A Rasa connector for turn.io",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="praekelt.org",
    author_email="dev@praekelt.org",
    url="https://github.com/praekeltfoundation/turn-rasa-connector",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Topic :: Communications :: Chat",
    ],
    license="BSD",
    keywords="rasa turn",
    project_urls={
        "Bug Tracker": "https://github.com/praekeltfoundation/turn-rasa-connector/"
        "issues",
        "Source Code": "https://github.com/praekeltfoundation/turn-rasa-connector",
    },
    install_requires=["rasa"],
)
