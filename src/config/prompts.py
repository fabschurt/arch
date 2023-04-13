INSTALL_CONFIRM = """
This install script assumes the following characteristics for the target system:
  * UEFI boot (without Secure Boot)
  * Intel CPU and integrated GPU
  * wired Internet connection (with DHCP)
Any other type of configuration is not supported.
Confirm installation? (y/n)
=> """

INSTALL_DISK = """
Available disks:

{choices}

Which disk should Arch be installed to? (CAUTION: the disk will be completely erased!)
=> """

PROCESSOR_BRAND = """
What is the brand of your CPU? ({choices})
=> """
