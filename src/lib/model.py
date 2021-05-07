import re
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, Optional


@dataclass(frozen=True)
class ByteCount:
    amount: int

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError('Byte count must be a positive integer.')

    def __int__(self) -> int:
        return self.amount


@dataclass(frozen=True)
class Disk:
    PATH_PATTERN = '/dev/[a-z]+'

    path: str

    def __post_init__(self) -> None:
        if not re.search(f'^{self.PATH_PATTERN}$', self.path):
            raise ValueError('Invalid disk path.')

    def __str__(self) -> str:
        return self.path


@dataclass(frozen=True)
class Partition:
    PATH_PATTERN = r'/dev/[a-z]+\d+'

    path: str

    def __post_init__(self) -> None:
        if not re.search(f'^{self.PATH_PATTERN}$', self.path):
            raise ValueError('Invalid disk partition path.')

    def __str__(self) -> str:
        return self.path


@dataclass(frozen=True)
class PartitionMap:
    boot: Partition
    root: Partition


class ProcessorBrand(Enum):
    AMD = 'amd'
    INTEL = 'intel'

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BootstrapParameters:
    install_disk: Disk
    processor_brand: Optional[ProcessorBrand]
    total_memory: ByteCount
