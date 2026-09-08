from dataclasses import asdict, dataclass
from enum import Enum
from urllib.parse import urlparse
import re
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    RESOLVING = "resolving"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


def safe_filename(value: str, fallback: str = "download.bin") -> str:
    value = value.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r'[<>:"|?*\x00-\x1f]', "_", value).rstrip(". ")
    return value[:240] or fallback


def filename_from_link(link: str) -> str:
    parsed = urlparse(link)
    fragment = parsed.fragment.strip()
    if fragment:
        return safe_filename(fragment)
    file_id = parsed.path.rstrip("/").split("/")[-1]
    return safe_filename(file_id or "download.bin")


@dataclass
class DownloadJob:
    url: str
    filename: str = ""
    id: str = ""
    status: JobStatus = JobStatus.PENDING
    downloaded: int = 0
    total: int = 0
    error: str = ""
    selected: bool = True

    def __post_init__(self):
        self.id = self.id or uuid.uuid4().hex
        self.filename = safe_filename(self.filename or filename_from_link(self.url))
        if isinstance(self.status, str):
            self.status = JobStatus(self.status)

    def to_dict(self):
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
