# polymer_extractor/utils/file_utils.py

"""
File utilities for Polymer NLP Extractor.

Provides robust, logged functions for zipping and unzipping directories,
with preemptive error handling to avoid silent failures.
"""

import shutil
import os
from pathlib import Path
from typing import Union

from polymer_extractor.utils.logging import Logger

logger = Logger()


def zip_directory(
    input_dir: Union[str, Path],
    archive_path: Union[str, Path] = None,
    format: str = "zip"
) -> Path:
    """
    Compress an entire directory into a single archive.

    Parameters
    ----------
    input_dir : str | Path
        Path to the directory you want to zip.
    archive_path : str | Path, optional
        Base path (without extension) for the archive. If omitted, the archive
        will be created alongside input_dir with the same name.
    format : str, optional
        Format for shutil.make_archive (e.g., "zip", "gztar", "tar").

    Returns
    -------
    Path
        Path to the created archive file.

    Raises
    ------
    ValueError
        If input_dir is not a directory.
    RuntimeError
        If the zipping process fails.
    """
    try:
        input_path = Path(input_dir)
        if not input_path.is_dir():
            msg = f"{input_path} is not a directory"
            logger.error(
                msg,
                source="file_utils.zip_directory",
                category="system",
                event_type="zip_error"
            )
            raise ValueError(msg)

        # determine archive base name
        if archive_path is None:
            archive_path = input_path.with_name(input_path.name)
        archive_base = Path(archive_path)

        logger.info(
            f"Zipping directory {input_path} to {archive_base}.{format}",
            source="file_utils.zip_directory",
            category="system",
            event_type="zip_start"
        )

        archive_file = shutil.make_archive(
            base_name=str(archive_base),
            format=format,
            root_dir=str(input_path),
            base_dir="."
        )
        archive_path_final = Path(archive_file)

        logger.info(
            f"Created archive {archive_path_final}",
            source="file_utils.zip_directory",
            category="system",
            event_type="zip_complete"
        )
        return archive_path_final

    except Exception as e:
        logger.error(
            f"Failed to zip directory {input_dir}: {e}",
            source="file_utils.zip_directory",
            category="system",
            event_type="zip_error"
        )
        raise RuntimeError(f"zip_directory error: {e}")


def unzip_archive(
    archive_path: Union[str, Path],
    extract_dir: Union[str, Path]
) -> None:
    """
    Extract a zip/gztar/tar archive into a directory.

    Parameters
    ----------
    archive_path : str | Path
        Path to the archive file.
    extract_dir : str | Path
        Directory where contents will be unpacked. Created if missing.

    Raises
    ------
    FileNotFoundError
        If the archive does not exist.
    RuntimeError
        If extraction fails.
    """
    try:
        archive_file = Path(archive_path)
        if not archive_file.exists():
            msg = f"Archive not found at {archive_file}"
            logger.error(
                msg,
                source="file_utils.unzip_archive",
                category="system",
                event_type="unzip_error"
            )
            raise FileNotFoundError(msg)

        extract_path = Path(extract_dir)
        os.makedirs(extract_path, exist_ok=True)

        logger.info(
            f"Extracting archive {archive_file} to {extract_path}",
            source="file_utils.unzip_archive",
            category="system",
            event_type="unzip_start"
        )

        shutil.unpack_archive(str(archive_file), str(extract_path))

        logger.info(
            f"Extraction complete to {extract_path}",
            source="file_utils.unzip_archive",
            category="system",
            event_type="unzip_complete"
        )

    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(
            f"Failed to extract archive {archive_path}: {e}",
            source="file_utils.unzip_archive",
            category="system",
            event_type="unzip_error"
        )
        raise RuntimeError(f"unzip_archive error: {e}")

def sanitize_name(name: str) -> str:
    """
    Sanitize a string for use as a safe file or folder name.
    Replaces /, \, -, spaces with underscores.
    """
    return name.replace("/", "_").replace("\\", "_").replace("-", "_").replace(" ", "_")
