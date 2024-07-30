"""
Stiefelsystem subcommand.
"""

from .config import Config

import argparse
import abc


class Subcommand(abc.ABC):
    """
    Base for a stiefelsystem module.
    """

    def __init__(self):
        pass

    @abc.abstractclassmethod
    def register(cls, subparser: argparse.ArgumentParser):
        """ fill the given subparser with command-specific options """
        raise NotImplementedError()

    @abc.abstractmethod
    def run(self, args, cfg):
        """
        execute the subcommand, given parsed args and the processed
        configuration. return the program's exit code.
        """
        raise NotImplementedError()


class ConfigDefault:
    """
    used as special default argument value.
    when not overridden by the cli arg,
    we take a configuration entry as value.
    """
    def __init__(self, config_key, formatter=None):
        self.key = config_key
        self.formatter = formatter

    def get_value(self, cfg):
        """
        get the stored key from the configuration.
        if there was a formatter set, apply it to the configuration value.
        """
        cfgkeys = self.key.split(".")
        for member in cfgkeys[:-1]:
            cfg = getattr(cfg, member)
        ret = getattr(cfg, cfgkeys[-1])
        if self.formatter:
            ret = self.formatter(ret)
        return ret

    def __str__(self):
        """
        string representation of this default option,
        displayed in the cli help text.
        """
        if self.formatter:
            return f"config's {self.formatter(self.key)}"
        else:
            return f"config's {self.key}"
