#!/usr/bin/env bash
set -Eeu -o pipefail

main() {
  systemctl stop reflector

  timedatectl set-ntp 1

  local -r CONFIRMATION_MSG="$(cat <<'MSG'
This install script assumes this computer boots with UEFI and is connected to the Internet through DHCP.
Any other type of configuration is not supported.
Confirm installation? (y/n)
MSG
  )"

  local installation_confirmed=''

  while [[ ! "$installation_confirmed" =~ ^[YyNn]$  ]]; do
    echo
    read -p "${CONFIRMATION_MSG} " installation_confirmed
  done

  if [[ "$installation_confirmed" =~ ^[Nn]$ ]]; then
    exit 1
  fi

  local target_disk=''

  while [[ -z "$target_disk" || ! "$target_disk" =~ ^/dev/[a-z\d]+$ || ! -e "$target_disk" ]]; do
    echo
    fdisk --list
    echo
    read -p 'Which disk should Arch be installed to? (CAUTION: the disk will be completely erased!) ' target_disk
  done

  wipefs --all "$target_disk"
  parted "$target_disk" mklabel gpt
  parted "$target_disk" mkpart uefi_boot fat32 1MiB 321MiB
  parted "$target_disk" mkpart root ext4 321MiB 100%
  parted "$target_disk" set 1 esp on

  local -r BOOT_PART="$target_disk"1
  local -r ROOT_PART="$target_disk"2

  mkfs.fat -F 32 "$BOOT_PART"
  mkfs.ext4 "$ROOT_PART"

  local -r ROOT_DIR=/mnt

  mount --options noatime "$ROOT_PART" "$ROOT_DIR"
  mkdir "${ROOT_DIR}/boot"
  mount --options noatime "$BOOT_PART" "${ROOT_DIR}/boot"

  local -r SWAPFILE_PATH="${ROOT_DIR}/swapfile"
  local -r AVAILABLE_MEMORY="$(free --bytes | awk 'match($0, /^Mem: +([0-9]+) /, matches) { print matches[1] }')"

  if [[ -z "$AVAILABLE_MEMORY" ]]; then
    echo
    echo '[ERROR] Unable to fetch the amount of RAM available on the system.'

    exit 1
  fi

  fallocate --length "$AVAILABLE_MEMORY" "$SWAPFILE_PATH"
  chmod 600 "$SWAPFILE_PATH"
  mkswap "$SWAPFILE_PATH"
  swapon "$SWAPFILE_PATH"

  reflector --latest 10 --sort rate --protocol https --save /etc/pacman.d/mirrorlist  --verbose

  local base_packages=(
    base
    linux-lts
    linux-firmware
    archlinux-keyring
    reflector
    sudo
    efibootmgr
    grub
  )

  local cpu_brand=''

  while [[ ! "$cpu_brand" =~ ^(intel|amd|other)$  ]]; do
    echo
    read -p "What is the brand of your CPU? (intel, amd, other) " cpu_brand
  done

  if [[ "$cpu_brand" != 'other' ]]; then
    base_packages+=("${cpu_brand}-ucode")
  fi

  pacstrap -G "$ROOT_DIR" "${base_packages[@]}"

  genfstab -U "$ROOT_DIR" | sed --regexp-extended 's/\t/ /g; s/ {2,}/ /g' > "${ROOT_DIR}/etc/fstab"

  local -r CHROOT_SCRIPT="$(cat <<'SCRIPT'
set -Eeu -o pipefail

main() {
  sed --in-place --regexp-extended 's/^#(Color)$/\1/' /etc/pacman.conf
  pacman-key --init
  pacman-key --populate archlinux

  ln --symbolic --force /usr/share/zoneinfo/Europe/Paris /etc/localtime
  hwclock --systohc

  local -r LOCALES=(
    en_US
    fr_FR
  )

  for locale in "${LOCALES[@]}"; do
    sed --in-place --regexp-extended "s/^#(${locale}\\.UTF-8 UTF-8 *)\$/\\1/" /etc/locale.gen
  done

  locale-gen

  cat <<'LOCALES' > /etc/locale.conf
LANG=en_US.UTF-8
LANGUAGE=en_US:en
LOCALES

  echo 'KEYMAP=fr-latin9' > /etc/vconsole.conf

  local hostname=''

  while [[ -z "$hostname" ]]; do
    echo
    read -p 'What is the hostname of this computer? ' hostname
  done

  echo "$hostname" > /etc/hostname

  cat <<HOSTS > /etc/hosts
127.0.0.1 localhost
::1 localhost
127.0.1.1 ${hostname}.localdomain ${hostname}
HOSTS

  local -r NETWORK_INTERFACES="$(ls /sys/class/net)"
  local target_interface='none'

  while [[ ! -z "$target_network_iface" && "$target_interface" != 'lo' ]]; do
    echo
    ip --color link show
    echo
    read -p 'Which network interface would you like to enable? (empty string to skip) ' target_interface
  done

  sed --in-place --regexp-extended 's/^# *(%wheel ALL=\(ALL\) ALL)$/\1/' /etc/sudoers
  rm /etc/skel/.bash_logout

  useradd --uid 1000 --groups wheel,sys --create-home fabschurt
  echo
  echo 'Please input the password for the main user:'
  passwd fabschurt

  local -Ar GRUB_OPTIONS=(
    [GRUB_TIMEOUT]=3
    [GRUB_CMDLINE_LINUX_DEFAULT]='"text"'
    [GRUB_GFXMODE]=1024x768x32,1024x768,auto
  )

  for option in "${!GRUB_OPTIONS[@]}"; do
    sed --in-place --regexp-extended "s/^${option}=.*\$/${option}=${GRUB_OPTIONS[$option]}/" /etc/default/grub
  done

  grub-install --target=x86_64-efi --bootloader-id=GRUB --efi-directory=/boot
  grub-mkconfig --output=/boot/grub/grub.cfg
}

main
SCRIPT
  )"

  arch-chroot "$ROOT_DIR" /bin/bash -c "$CHROOT_SCRIPT"
}

main
