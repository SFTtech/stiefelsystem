"""
NBD mapping setup
"""

from .util import install_platform_files
from ..util import FileEditor, command


def install(prefix, cfg):
    if 'dracut' in cfg.modules:
        # config files to include nbd support
        install_platform_files("dracut_nbd")

    if "system-arch" in cfg.modules:
        if 'dracut' in cfg.modules:
            raise NotImplementedError("not yet verified")
            install_platform_files('arch_dracut')

        else:
            install_platform_files('mkinitcpio_nbd')


def configure():
    raise NotImplementedError("not yet verified to work")

    edit = FileEditor('/etc/mkinitcpio.conf')
    edit.load_from('/etc/mkinitcpio.conf')
    edit.edit_bash_list('BINARIES', {'`which ifrename`': 'at-end'})
    edit.edit_bash_list('MODULES', {'amdgpu': 'at-end', 'i915': 'at-end'})

    changes = {'autodetect': 'remove'}
    if 'nbd' in cfg.modules:
        changes['nbd'] = 'before-fsck'
    edit.edit_bash_list('HOOKS', changes)
    # TODO: allow bypassing the consent question
    edit.write()

    # post-hook: re-generate initramfs
    #command('mkinitcpio', '-p', 'linux')
