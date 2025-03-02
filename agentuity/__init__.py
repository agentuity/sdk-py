import importlib.metadata

try:
    __version__ = importlib.metadata.version(__name__)
    print(f"Version: {__version__}")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"
