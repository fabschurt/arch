import re

from os import makedirs, chmod
from signal import SIGINT, signal
from sys import exit
from typing import Optional

from src.lib.utils import handle_sigint, run, write_to_file
from src.lib.model import Disk, PartitionMap, ProcessorBrand, ByteCount, BootstrapParameters
import src.config.paths
import src.config.prompts


def _get_available_disks() -> set[str]:
    fdisk_output = run('fdisk --list', capture_output=True).stdout
    disks = re.findall(f'^Disk ({Disk.PATH_PATTERN}):', fdisk_output, re.M)

    return {disk for disk in disks if not re.search(r'^/dev/loop\d+$', disk)}


def _get_total_memory() -> ByteCount:
    free_output = run('free --bytes', capture_output=True).stdout
    match = re.search(r'^Mem: +(?P<bytes>\d+) ', free_output, flags=re.M)

    return ByteCount(amount=int(match.group('bytes')))


def confirm_installation() -> None:
    response = None

    while response not in {'Y', 'y', 'N', 'n'}:
        response = input(prompts.INSTALL_CONFIRM)

    if response in {'N', 'n'}:
        exit(1)


def select_install_disk() -> Disk:
    disk_choices = _get_available_disks()
    install_disk = None
    prompt = prompts.INSTALL_DISK.format(choices='\n'.join([f' -> {disk}' for disk in disk_choices]))

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
    prompt = prompts.PROCESSOR_BRAND.format(choices=', '.join(proc_choices))

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

    run('systemctl stop reflector')


def enable_ntp() -> None:
    print('\nActivating NTP time synchronization...')

    run('timedatectl set-ntp 1')


def wipe_disk(disk: Disk) -> None:
    print(f'\nWiping disk {disk}...')

    run(f'wipefs --all {disk}')


def partition_disk(disk: Disk) -> PartitionMap:
    print(f'\nPartitioning disk {disk}...')

    run(f'parted {disk} mklabel gpt')
    run(f'parted {disk} mkpart uefi_boot fat32 1MiB 385MiB')
    run(f'parted {disk} mkpart root ext4 385MiB 100%')
    run(f'parted {disk} set 1 esp on')

    return PartitionMap(
        boot=Partition(f'{disk}1'),
        root=Partition(f'{disk}2')
    )


def format_partitions(partitions: PartitionMap) -> None:
    print('\nFormatting partitions...')

    run(f'mkfs.fat -F 32 {partitions.boot}')
    run(f'mkfs.ext4 {partitions.root}')


def mount_partitions(partitions: PartitionMap) -> None:
    print('\nMounting partitions...')

    run(f'mount --options noatime {partitions.root} {paths.CHROOT_PATH}')
    makedirs(paths.BOOT_DIR_PATH, mode=0o755, exist_ok=True)
    run(f'mount --options noatime {partitions.boot} {paths.BOOT_DIR_PATH}')


def create_swapfile(size: ByteCount) -> None:
    print('\nCreating swapfile...')

    run(f'fallocate --length {int(size)} {paths.SWAPFILE_PATH}')
    chmod(paths.SWAPFILE_PATH, 0o600)
    run(f'mkswap {paths.SWAPFILE_PATH}')


def enable_swap() -> None:
    print('\nEnabling swap...')

    run(f'swapon {paths.SWAPFILE_PATH}')


def update_mirror_list() -> None:
    print('\nUpdating mirror list...')

    run('reflector --verbose --protocol https --country France --latest 10 --sort rate --save /etc/pacman.d/mirrorlist')


def init_pacman_keyring() -> None:
    print('\nInitializing pacman keyring...')

    run('pacman-key --init')
    run('pacman-key --populate archlinux')


def install_base_system(processor_brand: Optional[ProcessorBrand]) -> None:
    print('\nInstalling base system...')

    base_packages = BASE_PACKAGES.copy()

    if processor_brand is not None:
        base_packages.add(f'{processor_brand}-ucode')

    run(f'pacstrap {paths.CHROOT_PATH} {" ".join(base_packages)}')


def generate_fstab() -> None:
    print('\nGenerating fstab...')

    fstab = run(f'genfstab -U {paths.CHROOT_PATH}', capture_output=True).stdout

    for pattern in {r'\t+', ' {2,}'}:
        fstab = re.sub(pattern, ' ', fstab, flags=re.M)

    write_to_file(f'{paths.CHROOT_PATH}/etc/fstab', fstab)


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
