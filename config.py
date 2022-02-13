"""
Configuration loader.

Loads the config from config.yaml when imported.

See config-example.yaml for an example configuration.
"""
import os

import yaml


def ensure_bool(obj):
    """ raises an exception if obj is not bool """
    if not isinstance(obj, bool):
        raise TypeError(f"expected bool but got {obj!r}")
    return obj


def ensure_string(obj):
    """ raises an exception if obj is not a string """
    if not isinstance(obj, str):
        raise TypeError(f"expected string but got {obj!r}")
    return obj


def ensure_stringlist(obj):
    """ raises an exception if obj is not a list of strings """
    if not isinstance(obj, list):
        raise TypeError(f"expected list of strings but got {obj!r}")
    for entry in obj:
        ensure_string(entry)
    return obj


def ensure_stringdict(obj):
    """ raises an exception if obj is not a dict with string values """
    if not isinstance(obj, dict):
        raise TypeError(f"expected dict of string values but got {obj!r}")
    for entry in obj.values():
        ensure_string(entry)
    return obj


class Config:
    """
    Global configuration object; contains sub-objects for the various
    configurable aspects.
    """
    def __init__(self, filename):
        with open(filename) as config_fileobj:
            raw = yaml.load(config_fileobj, Loader=yaml.SafeLoader)

        self.mod_config = {}
        for module, module_raw in raw['module-configs'].items():
            self.mod_config[module] = MODULE_CONFIG_CLASSES[module](module_raw)

        self.modules = {}
        for module in ensure_stringlist(raw['modules']):
            self.modules[module] = self.mod_config.get(module)

        self.boot = BootConfig(raw['boot'])
        self.autokexec = AutoKexecConfig(raw['autokexec'])
        self.server_setup = ServerSetupConfig(raw['server-setup'])
        self.initrd = InitRDConfig(raw['initrd'])
        self.packing = PackingConfig(raw['initrd']['packing'])
        self.path = PathConfig(raw['paths'])

        for mod_config in self.modules.values():
            if mod_config:
                mod_config.apply(self)


class BootConfig:
    """
    Boot configuration
    """
    def __init__(self, raw):
        self.disk = ensure_string(raw['disk'])

        self.method = ensure_string(raw['part']['type'])
        if self.method == "plain":
            self.luks_block = None
            self.part = ensure_string(raw['part']['block'])

        elif self.method == "luks":
            self.luks_block = ensure_string(raw['part']['luks_block'])
            self.part = ensure_string(raw['part']['block'])

        else:
            raise ValueError(f"unknown boot disk method {self.method!r}")

        self.kernel = ensure_string(raw['load']['kernel'])
        self.initrd = ensure_string(raw['load']['initrd'])
        self.cmdline = ensure_stringlist(raw['load']['cmdline'])


class AutoKexecConfig:
    """
    Configuration for stiefel-autokexec service that runs on the laptop
    """
    def __init__(self, raw):
        self.mac_detection = ensure_bool(raw['mac_detection'])
        self.broadcast = ensure_bool(raw['broadcast'])
        if self.mac_detection:
            self.macs = ensure_stringlist(raw['macs'])
        else:
            self.macs = []



class ServerSetupConfig:
    """
    server system setup information
    """
    def __init__(self, raw):
        self.stiefelsystem_kernel = ensure_string(raw['stiefelsystem-kernel'])
        self.stiefelsystem_initrd = ensure_string(raw['stiefelsystem-initrd'])
        self.cmdline = ensure_stringlist(raw['cmdline'])


class InitRDConfig:
    """
    initrd creation parameters
    """
    def __init__(self, raw):
        self.include_packages = ensure_stringlist(raw['include-packages'])
        self.shell = ensure_string(raw['shell'])
        self.password = ensure_string(raw['password'])


class PackingConfig:
    """
    initrd CPIO packer parameters
    """
    def __init__(self, raw):
        self.compressor = ensure_string(raw['compressor'])
        self.exclude_paths = ensure_stringlist(raw['exclude-paths'])
        self.exclude_packages = ensure_stringlist(raw['exclude-packages'])


class PathConfig:
    """
    The various internal paths where the scripts operate.
    """
    def __init__(self, raw):
        self.cache = ensure_string(raw['cache'])
        self.work = ensure_string(raw['workdir'])

        self.workpaths = {
            key: os.path.join(self.work, ensure_string(value))
            for key, value in raw['workdir-subpaths'].items()
        }

        self.cpio = self.workpaths['cpio']
        self.initrd = self.workpaths['initrd']
        self.initrd_devel = self.workpaths['initrd-devel']


def module_config(module_name):
    """
    Decorator function to be used with module configs
    Enters the class into MODULE_CONFIG_CLASSES

    Module config classes must provide an 'apply' method which will be
    automatically called after the config has finished parsing,
    if the module is enabled. It will be passed the config as an argument.
    """
    def register_module(module_class):
        MODULE_CONFIG_CLASSES[module_name] = module_class
        return module_class
    return register_module

# see module_config().
MODULE_CONFIG_CLASSES = {}


@module_config("debug")
class ModuleConfigDebug:
    def __init__(self, raw):
        self.better_shell = ensure_string(raw['better-shell'])
        self.dont_exclude_packages = ensure_bool(raw['dont-exclude-packages'])
        self.dont_exclude_paths = ensure_bool(raw['dont-exclude-paths'])
        self.faster_compressor = ensure_string(raw['faster-compressor'])
        self.extra_packages = ensure_stringlist(raw['extra-packages'])

    def apply(self, cfg):
        # modify the initrd creation and packing configuration to install more
        # utilities, increasing the initrd usability
        cfg.initrd.include_packages.extend(self.extra_packages)
        cfg.initrd.shell = self.better_shell
        if self.dont_exclude_paths:
            cfg.packing.exclude_paths.clear()
        if self.dont_exclude_packages:
            cfg.packing.exclude_packages.clear()
        cfg.packing.compressor = self.faster_compressor


@module_config("clevo-fancontrol")
@module_config("r8152")
class ModuleConfigGenericURL:
    def __init__(self, raw):
        self.url = ensure_string(raw['url'])

    def apply(self, cfg):
        pass

# load the config on module initialization
CONFIG = Config('config.yaml')
