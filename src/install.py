#!/usr/bin/env python
from fileinput import FileInput
from os import symlink, unlink
from os.path import exists
from signal import SIGINT, signal
from typing import NamedTuple, Optional
import re
import subprocess as sp


SYSTEM_LOCALES = {
    'en_US',
    'fr_FR',
}

SYSTEM_TIMEZONE = 'Europe/Paris'

CONSOLE_KEYMAP = 'fr-latin9'

ADMIN_USER_ID = 1000

CONF_LOCALES = """
LANG=en_US.UTF-8
LANGUAGE=en_US:en
"""

CONF_HOSTS = """
127.0.0.1 localhost
::1 localhost
127.0.1.1 {hostname}.localdomain {hostname}
"""

CONF_GRUB = """
[GRUB_TIMEOUT]=3
[GRUB_CMDLINE_LINUX_DEFAULT]="text"
[GRUB_GFXMODE]=1024x768x32,1024x768,auto
"""

PROMPT_HOSTNAME = """
What is the hostname of this computer?
=> """

PROMPT_ADMIN_USERNAME = """
What is the name of the admin user?
=> """

PROMPT_ADMIN_PASSWORD = """
Please now input the password for the admin user:
"""


class InstallParameters(NamedTuple):
    hostname: str
    admin_username: str


def _handle_sigint(signal: int, frame: Optional[object]):
    exit(1)


def _exec(cmd: str, *, capture_output: bool = False) -> sp.CompletedProcess:
    capture_args = {'stdout': sp.PIPE} if capture_output else {}

    return sp.run(cmd.split(), check=True, text=True, stderr=sp.STDOUT, **capture_args)


#def _search_in_file(file_path: str, search_pattern: str) -> Optional[re.Match]:
#    with FileInput(file_path) as file:
#        for line in file:
#            match = re.search(search_pattern, line)
#
#            if match is not None:
#                return match
#
#    return None


def _write_to_file(file_path: str, content: str) -> None:
    with open(file_path, mode='w') as file:
        print(content.strip(), file=file)


def _replace_in_file(file_path: str, search_pattern: str, replacement: str) -> None:
    with FileInput(file_path, inplace=True) as file:
        for line in file:
            print(re.sub(search_pattern, replacement, line), end='')


def _delete_file(file_path: str) -> None:
    if exists(file_path):
        unlink(file_path)


def _hostname_is_valid(hostname: str) -> bool:
    return bool(hostname) and re.search(r'^[a-z\d-]+$', hostname)


def _username_is_valid(name: str) -> bool:
    return bool(name) and re.search(r'^\w+$', name, re.A)


def _user_exists(id: int) -> bool:
    id_output = _exec(f'id {id}', capture_output=True).stdout

    return not id_output.endswith(': no such user')


def select_hostname() -> str:
    hostname = None

    while not _hostname_is_valid(hostname):
        hostname = input(PROMPT_HOSTNAME)

    return hostname


def select_admin_username() -> None:
    name = None

    while not _username_is_valid(name):
        name = input(PROMPT_ADMIN_USERNAME)

    return name


def gather_install_parameters():
    return InstallParameters(
        hostname=select_hostname(),
        admin_username=select_admin_username(),
    )


def create_admin_user(name: str) -> None:
    if _user_exists(ADMIN_USER_ID):
        return

    print('\nCreating admin user...')

    _exec(f'useradd --uid {ADMIN_USER_ID} --groups wheel,sys --create-home {name}')
    print(PROMPT_ADMIN_PASSWORD)
    _exec(f'passwd {name}')


def activate_sudoers() -> None:
    print('\nActivating sudoers...')

    _replace_in_file('/etc/sudoers', r'^# *(%wheel ALL=\(ALL\) ALL)$', r'\1')


def enable_pacman_colors() -> None:
    print('\nEnabling pacman colored output...')

    _replace_in_file('/etc/pacman.conf', r'^#(Color)$', r'\1')


def configure_timezone() -> None:
    print('\nConfiguring timezone...')

    _delete_file('/etc/localtime')
    symlink(f'/usr/share/zoneinfo/{SYSTEM_TIMEZONE}', '/etc/localtime')


def sync_hardware_clock() -> None:
    print('\nSyncing system clock to hardware clock...')

    _exec('hwclock --systohc')


def configure_locales() -> None:
    print('\nConfiguring locales...')

    for locale in SYSTEM_LOCALES:
        _replace_in_file(
            '/etc/locale.gen',
            r'^#({locale}\.UTF-8 UTF-8 *)$'.format(locale=re.escape(locale)),
            r'\1'
        )

    _exec('locale-gen')
    # TODO: Use localectl here instead of editing the file manually
    _write_to_file('/etc/locale.conf', CONF_LOCALES)


def configure_keyboard() -> None:
    print('\nConfiguring keyboard...')

    # TODO: Use localectl here instead of editing the file manually
    _write_to_file('/etc/vconsole.conf', f'KEYMAP={CONSOLE_KEYMAP}')


def configure_hosts(hostname: str) -> str:
    print('\nConfiguring hosts...')

    _write_to_file('/etc/hostname', hostname)
    _write_to_file('/etc/hosts', CONF_HOSTS.format(hostname=hostname))


def configure_grub() -> None:
    #sed --in-place --regexp-extended "s/^${option}=.*\$/${option}=${GRUB_OPTIONS[$option]}/" /etc/default/grub


def install_grub() -> None:
    command('grub-install --target=x86_64-efi --bootloader-id=GRUB --efi-directory=/boot')
    command('grub-mkconfig --output=/boot/grub/grub.cfg')


def cleanup() -> None:
    print('\nCleaning up...')

    _delete_file('/etc/skel/.bash_logout')


def main() -> None:
    signal(SIGINT, _handle_sigint)

    install_params = gather_install_parameters()

    create_admin_user(install_params.admin_username)
    activate_sudoers()

    enable_pacman_colors()

    configure_timezone()
    sync_hardware_clock()
    configure_locales()
    configure_keyboard()

    configure_hosts(install_params.hostname)
    #configure_network_ifaces()

    #configure_grub()
    #install_grub()

    cleanup()


if __name__ == '__main__':
    main()
