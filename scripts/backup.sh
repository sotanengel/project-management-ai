#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="${BACKUP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_DEST_DIR="${BACKUP_DEST_DIR:-${ROOT_DIR}/backups}"
PMDF_STORE_PATH="${PMDF_STORE_PATH:-${ROOT_DIR}/data/pmdf-store}"
uv run python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('${ROOT_DIR}') / 'scripts'))
from backup_restore_lib import create_backup
p = create_backup(
    root_dir=Path('${ROOT_DIR}'),
    dest_dir=Path('${BACKUP_DEST_DIR}'),
    pmdf_store_path=Path('${PMDF_STORE_PATH}'),
)
print(p)
"
