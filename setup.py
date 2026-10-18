from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

class BuildPy(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent / "workflows"
        target = Path(self.build_lib) / "pangene_workflows" / "workflows"
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(source.iterdir()):
            if path.is_file() and path.suffix in {".sh", ".py", ".toml", ".tsv"}:
                self.copy_file(str(path), str(target / path.name))

setup(cmdclass={"build_py": BuildPy})
