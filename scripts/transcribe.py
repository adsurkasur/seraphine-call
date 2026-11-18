#!/usr/bin/env python3
"""Portable STT adapter; no machine-specific wake-on-LAN, SSH or credentials."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio_path')
    parser.add_argument('-l', '--language', default='')
    args = parser.parse_args()
    path = Path(args.audio_path).resolve()
    if not path.is_file():
        print('Recording not found', file=sys.stderr)
        return 1
    url = os.getenv('SERA_WHISPER_URL', 'http://127.0.0.1:9000').rstrip('/')
    cmd = ['curl', '-fsS', '--max-time', '85', '-X', 'POST',
           url + '/v1/audio/transcriptions', '-F', 'file=@' + str(path),
           '-F', 'model=' + os.getenv('SERA_WHISPER_MODEL', 'whisper-1')]
    if args.language:
        cmd += ['-F', 'language=' + args.language]
    try:
        response = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if response.returncode:
            raise ValueError('STT service unavailable')
        data = json.loads(response.stdout)
        if not isinstance(data.get('text'), str):
            raise ValueError('Invalid STT response')
        print(data['text'].strip())
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print('Speech recognition service request failed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
