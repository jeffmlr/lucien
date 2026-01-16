"""
Subprocess worker for file extraction.

Isolates extraction in separate processes to prevent memory leaks
from accumulating in the main process.
"""

import contextlib
import gc
import io
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from multiprocessing import Queue

from .config import LucienSettings
from .extractors import ExtractionResult
from .pipeline import ExtractionPipeline


def extract_file_worker(
    file_info: Dict[str, Any],
    config_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
    extracted_text_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Extract a single file in a subprocess.
    
    Args:
        file_info: Dictionary with 'id', 'path', 'sha256'
        config_path: Path to config file (optional)
        db_path: Path to database (optional, overrides config)
        extracted_text_dir: Path to extracted text directory (optional, overrides config)
    
    Returns:
        Dictionary with extraction result: status, method, output_path, error
    """
    try:
        # Load config
        if config_path:
            config = LucienSettings.load_from_yaml(config_path)
        else:
            config = LucienSettings.load()
        
        # Override paths if provided
        if db_path:
            config.index_db = db_path
        if extracted_text_dir:
            config.extracted_text_dir = extracted_text_dir
        
        # Create pipeline (this will create new extractors in this process)
        from .db import Database
        database = Database(config.index_db)
        pipeline = ExtractionPipeline(config, database)
        
        # Extract file
        file_path = Path(file_info["path"])
        result = pipeline.extract_file(
            file_info["id"],
            file_path,
            file_info["sha256"]
        )

        # Prepare result as dictionary (serializable)
        result_dict = {
            "status": result.status,
            "method": result.method,
            "output_path": str(result.output_path) if result.output_path else None,
            "error": result.error,
        }

        # Clear result object explicitly
        del result

        # Force garbage collection to free memory immediately
        # This is critical for Docling which loads heavy ML models
        gc.collect()

        # Clear torch cache if available (Docling uses torch)
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Also clear CPU cache
            if hasattr(torch, 'mps') and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except ImportError:
            pass  # torch not available, skip

        return result_dict
    except Exception as e:
        # Catch any exception and return as failed
        return {
            "status": "failed",
            "method": "unknown",
            "output_path": None,
            "error": f"Worker error: {type(e).__name__}: {e}",
        }


def extract_file_worker_subprocess(
    file_info: Dict[str, Any],
    config_path: Optional[Path],
    db_path: Optional[Path],
    extracted_text_dir: Optional[Path],
    result_queue: Queue,
) -> None:
    """
    Subprocess wrapper that puts result in queue.
    
    This function is designed to be picklable for multiprocessing.
    """
    try:
        result_dict = extract_file_worker(
            file_info,
            config_path=config_path,
            db_path=db_path,
            extracted_text_dir=extracted_text_dir,
        )
        result_queue.put(("success", result_dict))
    except Exception as e:
        result_queue.put(("error", {
            "status": "failed",
            "method": "unknown",
            "output_path": None,
            "error": f"Worker exception: {type(e).__name__}: {e}",
        }))


def extract_file_for_pool(args_tuple: tuple) -> tuple:
    """
    Worker function for multiprocessing.Pool.
    
    This is a module-level function that can be pickled.
    Accepts a tuple of (file_info_dict, config_path, db_path, extracted_text_dir).
    Returns (file_info, result_dict) tuple.
    
    Suppresses stderr to prevent duplicate error messages from parallel workers.
    """
    file_info_dict, config_path, db_path, extracted_text_dir = args_tuple
    
    # Suppress stderr to prevent duplicate error messages from parallel workers
    # PyPDF and other libraries print warnings/errors to stderr (e.g., "Ignoring wrong pointing object")
    # With multiple workers, we'd see the same error multiple times and it causes screen tear with Rich
    # Redirect stderr to /dev/null during extraction to keep the display clean
    with open(os.devnull, 'w') as devnull:
        with contextlib.redirect_stderr(devnull):
            try:
                result_dict = extract_file_worker(
                    file_info_dict,
                    config_path=config_path,
                    db_path=db_path,
                    extracted_text_dir=extracted_text_dir,
                )
                return (file_info_dict, result_dict)
            except Exception as e:
                # Errors are handled by returning failed status, no need to log here
                return (file_info_dict, {
                    "status": "failed",
                    "method": "unknown",
                    "output_path": None,
                    "error": f"Worker exception: {type(e).__name__}: {e}",
                })


if __name__ == "__main__":
    # Allow running as standalone script for testing
    import json
    
    if len(sys.argv) < 2:
        print("Usage: extract_worker.py <file_info_json> [config_path] [db_path] [extracted_text_dir]")
        sys.exit(1)
    
    file_info = json.loads(sys.argv[1])
    config_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    db_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    extracted_text_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    
    result = extract_file_worker(file_info, config_path, db_path, extracted_text_dir)
    print(json.dumps(result))
