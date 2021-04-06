#!/usr/bin/env bash
set -Eeu -o pipefail

install_packages() {
  echo 'Installing required packages…'

  local -r INSTALLED_PACKAGES=( $(cat config/packages.list | tr '\n' ' ') )

  yay -Syu --noconfirm
  yay -S --needed --noconfirm --answerclean All --answerdiff None --answeredit None "${INSTALLED_PACKAGES[@]}"
}

copy_dotfiles() {
  echo 'Copying dotfiles…'

  [[ ! -f ~/.bashrc.dist ]] && cp /etc/skel/.bashrc ~/.bashrc.dist

  cp -a src/ ~
}

build_file_tree() {
  echo 'Building file tree…'

  mkdir -p \
    ~/.ssh \
    ~/.cache \
    ~/.config \
    ~/.local/bin \
    ~/Dev \
    ~/Documents \
    ~/Downloads \
    ~/Dropbox \
    ~/Images

  touch \
    ~/.ssh/id_rsa.pub \
    ~/.ssh/id_rsa

  chmod 0700 \
    ~/.ssh

  chmod 0600 \
    ~/.ssh/id_rsa \
    ~/.secrets
}

list_manual_steps() {
  echo 'Everything done. Now you can:'
  echo '  * Set your SSH key pair up'
  echo '  * Configure authentication for GitHub CLI'
  echo '  * Open Chrome and Chromium, enable sync, and configure the DevTools'
  echo '  * Start Dropbox and link it to your account'
  echo '  * Configure a YouTube API key for `youtube-viewer`'
  echo '  * Add yourself into the `docker` user group and log into Docker Hub'
  echo '  * Add yourself into the `vboxusers` user group in order to be able to mount USB devices in VirtualBox'
  echo '  * Add yourself into the `sys` user group for CUPS administration'
}

main() {
  install_packages
  copy_dotfiles
  build_file_tree
  list_manual_steps
}

main "${1:-}"

exit 0
