from setuptools import find_packages, setup

requires = []

with open("requirements.txt", "r") as f:
    for resource in f.readlines():
        if not resource.startswith("git+"):
            requires.append(resource.strip())
        else:
            res = resource.strip()
            egg = res.split("#egg=")[1]
            requires.append("@".join([egg, res]))

setup(
    name="prozorro_risks",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    description="",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=requires,
)
