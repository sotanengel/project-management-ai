#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <archive.tar.gz> <restore_root_dir>" >&2
  exit 1
fi
uv run python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.') / 'scripts'))
from backup_restore_lib import restore_backup
restore_backup(archive_path=Path('$1'), restore_root=Path('$2'))
print('Restored to $2')
"
