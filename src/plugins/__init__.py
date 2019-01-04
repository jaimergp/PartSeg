import importlib
import pkgutil

def get_plugins():
    packages = pkgutil.iter_modules(__path__)
    return list(packages)


def register():
    print("plugins load", get_plugins())
    for el in get_plugins():
        importlib.import_module("." + el.name, __package__).register()
