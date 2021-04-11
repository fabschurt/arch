import re

from os import makedirs, chmod
from signal import SIGINT, signal
from sys import exit
from typing import Optional

from src.lib.utils import handle_sigint, command, write_to_file
from src.lib.model import Disk, PartitionMap, ProcessorBrand, ByteCount, BootstrapParameters
import src.config.constants as c
import src.config.prompts as p


def _get_available_disks() -> set[str]:
    fdisk_output = command('fdisk --list', capture_output=True).stdout
    disks = re.findall(f'^Disk ({Disk.PATH_PATTERN}):', fdisk_output, re.M)

    return {disk for disk in disks if not re.search(r'^/dev/loop\d+$', disk)}


def _get_total_memory() -> ByteCount:
    free_output = command('free --bytes', capture_output=True).stdout
    match = re.search(r'^Mem: +(?P<bytes>\d+) ', free_output, flags=re.M)

    return ByteCount(amount=int(match.group('bytes')))


def confirm_installation() -> None:
    response = None

    while response not in {'Y', 'y', 'N', 'n'}:
        response = input(p.INSTALL_CONFIRM)

    if response in {'N', 'n'}:
        exit(1)


def select_install_disk() -> Disk:
    disk_choices = _get_available_disks()
    install_disk = None
    prompt = p.INSTALL_DISK.format(choices='\n'.join([f' -> {disk}' for disk in disk_choices]))

    while install_disk not in disk_choices:
        install_disk = input(prompt)

    return Disk(path=install_disk)


def select_processor_brand() -> Optional[ProcessorBrand]:
    proc_brands = {
        **{member.value: member for member in ProcessorBrand},
        'other': None,
    }
    proc_choices = proc_brands.keys()
    proc_brand = None
    prompt = p.PROCESSOR_BRAND.format(choices=', '.join(proc_choices))

    while proc_brand not in proc_choices:
        proc_brand = input(prompt)

    return proc_brands[proc_brand]


def gather_install_parameters() -> BootstrapParameters:
    return BootstrapParameters(
        install_disk=select_install_disk(),
        processor_brand=select_processor_brand(),
        total_memory=_get_total_memory(),
    )


def stop_reflector() -> None:
    print('\nStopping Reflector service...')

    command('systemctl stop reflector')


def enable_ntp() -> None:
    print('\nActivating NTP time synchronization...')

    command('timedatectl set-ntp 1')


def wipe_disk(disk: Disk) -> None:
    print(f'\nWiping disk {disk}...')

    command(f'wipefs --all {disk}')


def partition_disk(disk: Disk) -> PartitionMap:
    print(f'\nPartitioning disk {disk}...')

    command(f'parted {disk} mklabel gpt')
    command(f'parted {disk} mkpart uefi_boot fat32 1MiB 321MiB')
    command(f'parted {disk} mkpart root ext4 321MiB 100%')
    command(f'parted {disk} set 1 esp on')

    return PartitionMap(
        boot=Partition(f'{disk}1'),
        root=Partition(f'{disk}2')
    )


def format_partitions(partitions: PartitionMap) -> None:
    print('\nFormatting partitions...')

    command(f'mkfs.fat -F 32 {partitions.boot}')
    command(f'mkfs.ext4 {partitions.root}')


def mount_partitions(partitions: PartitionMap) -> None:
    print('\nMounting partitions...')

    command(f'mount --options noatime {partitions.root} {c.CHROOT_PATH}')
    makedirs(c.BOOT_DIR_PATH, mode=0o755, exist_ok=True)
    command(f'mount --options noatime {partitions.boot} {c.BOOT_DIR_PATH}')


def create_swapfile(size: ByteCount) -> None:
    print('\nCreating swapfile...')

    command(f'fallocate --length {int(size)} {c.SWAPFILE_PATH}')
    chmod(c.SWAPFILE_PATH, 0o600)
    command(f'mkswap {c.SWAPFILE_PATH}')


def enable_swap() -> None:
    print('\nEnabling swap...')

    command(f'swapon {c.SWAPFILE_PATH}')


def update_mirror_list() -> None:
    print('\nUpdating mirror list...')

    command('reflector --verbose --protocol https --country France --latest 10 --sort rate --save /etc/pacman.d/mirrorlist')


def init_pacman_keyring() -> None:
    print('\nInitializing pacman keyring...')

    command('pacman-key --init')
    command('pacman-key --populate archlinux')


def install_base_system(processor_brand: Optional[ProcessorBrand]) -> None:
    print('\nInstalling base system...')

    base_packages = BASE_PACKAGES.copy()

    if processor_brand is not None:
        base_packages.add(f'{processor_brand}-ucode')

    command(f'pacstrap {c.CHROOT_PATH} {" ".join(base_packages)}')


def generate_fstab() -> None:
    print('\nGenerating fstab...')

    fstab = command(f'genfstab -U {c.CHROOT_PATH}', capture_output=True).stdout

    for pattern in {r'\t+', ' {2,}'}:
        fstab = re.sub(pattern, ' ', fstab, flags=re.M)

    write_to_file(f'{c.CHROOT_PATH}/etc/fstab', fstab)


def main() -> None:
    signal(SIGINT, handle_sigint)

    confirm_installation()
    install_params = gather_install_parameters()

    stop_reflector()
    enable_ntp()

    wipe_disk(install_params.install_disk)
    partitions = partition_disk(install_params.install_disk)
    format_partitions(partitions)
    mount_partitions(partitions)
    create_swapfile(install_params.total_memory)
    enable_swap()

    update_mirror_list()
    init_pacman_keyring()
    install_base_system(install_params.processor_brand)

    generate_fstab()


if __name__ == '__main__':
    main()
