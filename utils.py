import os


def create_dirs(path: str):
    directory_path = os.path.dirname(path)
    if not os.path.isfile(path):
        directory_path = path
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def build_path(path1: str, path2: str) -> str:
    return os.path.join(
        path1,
        path2
    ).rstrip('/')
