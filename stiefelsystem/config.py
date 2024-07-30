"""
Configuration loader.

Loads the config from config.yaml when imported.

See config-example.yaml for an example configuration.
"""
import logging
import os

import yaml

from pathlib import Path


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
    module_config_classes = dict()

    def __init__(self, cfgfilename, system_mode=False):
        # whether stiefelsystem runs in its repo or is installed system-wide
        self.system_mode = system_mode

        logging.info("reading config file %s...", cfgfilename)

        with open(cfgfilename) as config_fileobj:
            raw = yaml.safe_load(config_fileobj)

        stiefel_cfg = raw['stiefelsystem']

        self.mod_config = {}
        for module, module_raw in stiefel_cfg['module-configs'].items():
            logging.debug(f"processing module config for {module!r}")
            self.mod_config[module] = self.module_config_classes[module](module_raw)

        self.modules = {}
        for module in ensure_stringlist(stiefel_cfg['modules']):
            self.modules[module] = self.mod_config.get(module)


        self.boot = BootConfig(raw['boot'])
        self.autokexec = AutoKexecConfig(raw['autokexec'])
        self.server_setup = ServerSetupConfig(raw['server-setup'])
        self.initrd = InitRDConfig(raw['initrd'])
        self.packing = PackingConfig(raw['initrd']['packing'])
        self.path = PathConfig(stiefel_cfg['paths'])

        self.aes_key_location = self.path.state / "aes-key"

        for mod_config in self.modules.values():
            if mod_config:
                mod_config.apply(self)

    @classmethod
    def module_config(cls, module_name):
        """
        Decorator function to be used with module configs
        Enters the class into `module_config_classes`

        Module config classes must provide an 'apply' method which will be
        automatically called after the config has finished parsing,
        if the module is enabled. It will be passed the config as an argument.
        """
        def register_module(module_class):
            cls.module_config_classes[module_name] = module_class
            return module_class
        return register_module


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

        self.kernel = ensure_string(raw['kernel'])
        self.initrd = ensure_string(raw['initrd'])
        self.cmdline = ensure_stringlist(raw['cmdline'])


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
        self.stiefel_os_kernel = ensure_string(raw['stiefel-os-kernel'])
        self.stiefel_os_initrd = ensure_string(raw['stiefel-os-initrd'])
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
        # debootstrap downloads
        # TODO on debianoid systems, we could share it with the system
        #      package cache
        self.cache = Path(ensure_string(raw['cache_dir']))

        # where the resulting initramfs is stored
        self.state = Path(ensure_string(raw['state_dir']))

        # workdir, we create stiefelOS in here
        self.work = self.state / "work"

        # where the system is assembled
        self.initrd = self.work / "initrd"

        # overlayfs mounted over initrd, where additional development tools
        # are installed
        self.initrd_devel = self.work / "initrd-devel"

        # the packed initrd directory as archive
        self.cpio = self.work / "initrd.cpio"


@Config.module_config("debug")
class ModuleConfigDebug:
    def __init__(self, raw):
        self.better_shell = ensure_string(raw['better-shell'])
        self.dont_exclude_packages = ensure_bool(raw['dont-exclude-packages'])
        self.dont_exclude_paths = ensure_bool(raw['dont-exclude-paths'])
        self.faster_compressor = ensure_string(raw['faster-compressor'])
        self.extra_packages = ensure_stringlist(raw['extra-packages'])

    def apply(self, cfg):
        """
        modify the initrd creation and packing configuration to install more
        utilities, increasing the initrd usability
        """
        cfg.initrd.include_packages.extend(self.extra_packages)
        cfg.initrd.shell = self.better_shell
        if self.dont_exclude_paths:
            cfg.packing.exclude_paths.clear()
        if self.dont_exclude_packages:
            cfg.packing.exclude_packages.clear()
        cfg.packing.compressor = self.faster_compressor
