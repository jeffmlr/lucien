"""
macOS Finder tags management.

Applies native macOS tags to files using extended attributes.

TODO: Implement in Milestone 4 (v0.4)
"""

import subprocess
from pathlib import Path
from typing import List, Optional


def apply_finder_tags(file_path: Path, tags: List[str]) -> None:
    """
    Apply macOS Finder tags to a file.

    Uses xattr or the 'tag' CLI tool to set native macOS tags.

    Args:
        file_path: Path to file
        tags: List of tag names

    Raises:
        Exception: If tag application fails
    """
    if not tags:
        return

    # TODO: Implement tag application
    # Prefer xattr library approach:
    # import xattr
    # Use com.apple.metadata:_kMDItemUserTags extended attribute

    # Fallback to 'tag' CLI if available:
    # subprocess.run(['tag', '-a', ','.join(tags), str(file_path)])

    raise NotImplementedError("macOS tag application not yet implemented (Milestone 4)")


def get_finder_tags(file_path: Path) -> List[str]:
    """
    Get macOS Finder tags from a file.

    Args:
        file_path: Path to file

    Returns:
        List of tag names
    """
    # TODO: Implement tag reading
    raise NotImplementedError("macOS tag reading not yet implemented (Milestone 4)")


def remove_finder_tags(file_path: Path, tags: Optional[List[str]] = None) -> None:
    """
    Remove macOS Finder tags from a file.

    Args:
        file_path: Path to file
        tags: List of tags to remove (removes all if None)
    """
    # TODO: Implement tag removal
    raise NotImplementedError("macOS tag removal not yet implemented (Milestone 4)")


def check_tag_support() -> bool:
    """
    Check if macOS tag support is available.

    Returns:
        True if tags can be applied
    """
    # Check if running on macOS
    import platform
    if platform.system() != "Darwin":
        return False

    # Check if xattr is available
    try:
        import xattr
        return True
    except ImportError:
        pass

    # Check if 'tag' CLI is available
    try:
        result = subprocess.run(
            ["which", "tag"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


# Example implementation using xattr (for reference):
# import xattr
# import plistlib
#
# def apply_finder_tags_xattr(file_path: Path, tags: List[str]) -> None:
#     """Apply tags using xattr library."""
#     # Read existing tags
#     try:
#         existing = xattr.getxattr(str(file_path), 'com.apple.metadata:_kMDItemUserTags')
#         existing_tags = plistlib.loads(existing)
#     except OSError:
#         existing_tags = []
#
#     # Merge with new tags
#     all_tags = list(set(existing_tags + tags))
#
#     # Write back
#     plist_data = plistlib.dumps(all_tags)
#     xattr.setxattr(str(file_path), 'com.apple.metadata:_kMDItemUserTags', plist_data)
