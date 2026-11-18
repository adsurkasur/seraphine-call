import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

p = Path(__file__).parents[1] / 'scripts/transcribe.py'
spec = importlib.util.spec_from_file_location('transcribe', p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with tempfile.NamedTemporaryFile(suffix='.wav') as audio:
    with patch.object(sys, 'argv', ['transcribe.py', audio.name, '-l', 'en']), patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='{"text":"hello"}')) as run:
        assert m.main() == 0
        args = run.call_args.args[0]
        assert 'language=en' in args and 'file=@' + str(Path(audio.name).resolve()) in args
    with patch.object(sys, 'argv', ['transcribe.py', audio.name]), patch.object(m.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='not JSON')):
        assert m.main() == 1
print('Portable STT adapter contract PASS')
