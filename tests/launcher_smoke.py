"""Exercise real Windows entry points in an isolated path containing spaces/apostrophe."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='shinchan launch ') as temp:
    project=Path(temp)/"pet's project"
    project.mkdir()
    for directory in ('scripts','assets'):
        shutil.copytree(root/directory,project/directory)
    runtime=Path(temp)/'runtime'
    env={**os.environ,'PET_RUNTIME_DIR':str(runtime),'PET_TASKS_DIR':str(Path(temp)/'tasks'),
         'PET_PROGRESS_FILE':str(Path(temp)/'progress.txt'),'TELEAGENT_DB':str(Path(temp)/'missing.db'),
         'QT_QPA_PLATFORM':'offscreen','PYTHONUTF8':'1'}
    starter=project/'scripts/pet-start.py'
    ctl=project/'scripts/shinchan-pet.ps1'
    def run(args):
        result=subprocess.run(args,env=env,cwd=project,capture_output=True,text=True,encoding='utf-8',timeout=35)
        if result.returncode:
            raise AssertionError(result.stdout+'\n'+result.stderr)
        return result.stdout
    def wait_exit(pid):
        # PID removal happens just before interpreter shutdown; wait for the process
        # too, so Windows has released every log/DLL handle before temp cleanup.
        subprocess.run(['powershell.exe','-NoProfile','-Command',
                        f'Wait-Process -Id {int(pid)} -ErrorAction SilentlyContinue'],
                       capture_output=True,timeout=15)
    try:
        run([sys.executable,'-B',str(starter)])
        pid=(runtime/'host.pid').read_text()
        run([sys.executable,'-B',str(starter)])
        assert pid==(runtime/'host.pid').read_text(), 'duplicate instance'
        run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ctl),'-Command','stop'])
        wait_exit(pid)
        for _ in range(30):
            if not (runtime/'host.pid').exists():break
            time.sleep(.1)
        assert not (runtime/'host.pid').exists(), 'PID not cleaned'
        run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ctl),'-Command','start'])
        assert (runtime/'host.pid').exists()
        print('PASS: spaced/apostrophe path, Python start, repeated start, stop/PID cleanup, PowerShell control start.')
    finally:
        last_pid=(runtime/'host.pid').read_text() if (runtime/'host.pid').exists() else None
        subprocess.run([sys.executable,'-B',str(starter),'--stop'],env=env,capture_output=True,timeout=10)
        if last_pid:
            wait_exit(last_pid)
        for _ in range(50):
            if not (runtime/'host.pid').exists():break
            time.sleep(.1)
