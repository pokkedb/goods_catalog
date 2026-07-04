#!/bin/bash
# /pokke/databases/ 全体をGoogle Driveへ同期する（全プロジェクト共通のDB置き場のため一括バックアップ）。
# Dropbox(無料2GB)は空き容量が足りず、Google Drive(無料15GB)に変更した経緯あり。
# shared/cron_runner/daily.sh から呼び出される。差分のみ転送するため毎日実行しても軽量。
set -euo pipefail

rclone sync /pokke/databases/ gdrive:backup/pokke_databases/ --log-level INFO
