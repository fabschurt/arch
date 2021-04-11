INSTALL_CONFIRM = """
This install script assumes this computer boots with UEFI and is connected to the Internet through DHCP.
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
