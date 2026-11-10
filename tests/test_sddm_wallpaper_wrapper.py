"""Installed-layout process tests for the SDDM rotation wrapper."""
from __future__ import annotations
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).parents[1] / "dotfiles/dot_local/bin"
WRAPPER = SOURCE / "executable_ezwallpaper-sddm-rotate.py"

class InstalledWrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.bin = self.home / ".local/bin"; self.bin.mkdir(parents=True)
        self.runtime = self.home / "runtime"; self.runtime.mkdir(mode=0o700)
        self.lock = self.runtime / "ezwallpaper-rotate.lock"; self.lock.touch(mode=0o644); os.chmod(self.lock, 0o644)
        self.marker = self.home / "marker"; self.argv = self.home / "argv"
        deployed = self.bin / "ezwallpaper-sddm-rotate.py"; shutil.copy2(WRAPPER, deployed); deployed.chmod(0o755)
        self.rotator = self.bin / "ezwallpaper"; self.rotation(0)
        self.publisher = self.bin / "sddm-wallpaper-sync.py"; self.publish("pathlib.Path(MARK).write_text('ok')")

    def rotation(self, status):
        self.rotator.write_text("#!/usr/bin/env python3\nimport sys\n"
            f"open({str(self.argv)!r},'w').write('\\n'.join(sys.argv[1:]))\n"
            "print('rotator-out'); print('rotator-err',file=sys.stderr)\n"
            f"raise SystemExit({status})\n"); self.rotator.chmod(0o755)

    def publish(self, action):
        lines = action.strip().splitlines()
        body = "\n".join(" " + line.strip() for line in lines)
        self.publisher.write_text(
            "import os,pathlib,time,subprocess\n"
            f"MARK={str(self.marker)!r}; LOCK={str(self.lock)!r}\n"
            "def publish_after_owner_success():\n"
            " fd=next(int(x.name) for x in pathlib.Path('/proc/self/fd').iterdir() if x.name.isdigit() and os.readlink(x)==LOCK)\n"
            " st=os.stat(LOCK); assert (os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(st.st_dev,st.st_ino)\n"
            + body + "\n"
            "def cleanup_after_abort():\n pathlib.Path(MARK+'.cleanup').write_text('done')\n")

    def start(self, fd):
        env = os.environ | {"HOME":str(self.home),"XDG_RUNTIME_DIR":str(self.runtime),"PYTHONDONTWRITEBYTECODE":"1"}
        return subprocess.Popen([sys.executable,str(self.bin/'ezwallpaper-sddm-rotate.py')],env=env,pass_fds=(fd,),stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def test_installed_names_execution_argv_stream_passthrough(self):
        fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
        p=self.start(fd); os.close(fd); out,err=p.communicate(timeout=5)
        self.assertEqual(p.returncode,0,err.decode()); self.assertEqual(out,b'rotator-out\n'); self.assertIn(b'rotator-err\n',err)
        self.assertEqual(self.argv.read_text().splitlines(),['rotate','next','--profile',str(self.home/'.config/ezwallpaper/rotation-profile.json'),'--apply'])
        self.assertEqual(self.marker.read_text(),'ok')

    def test_rotator_23_suppresses_publisher(self):
        self.rotation(23); fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
        p=self.start(fd); os.close(fd); p.communicate(timeout=5)
        self.assertEqual(p.returncode,23); self.assertFalse(self.marker.exists())

    def test_publisher_errors_and_missing_install_are_nonfatal(self):
        for action in ("raise RuntimeError('oops')", "raise ValueError('oops')"):
            self.publish(action); fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
            p=self.start(fd); os.close(fd); p.communicate(timeout=5); self.assertEqual(p.returncode,0)
        self.publisher.unlink(); fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
        p=self.start(fd); os.close(fd); p.communicate(timeout=5); self.assertEqual(p.returncode,0)

    def test_lock_remains_held_through_real_publisher_and_then_releases(self):
        self.publish(f"pathlib.Path(MARK+'.entered').write_text('yes')\ntime.sleep(.4)\npathlib.Path(MARK).write_text('published')")
        fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX); p=self.start(fd); os.close(fd)
        try:
            deadline=time.monotonic()+4
            while not Path(str(self.marker)+'.entered').exists() and time.monotonic()<deadline: time.sleep(.01)
            self.assertTrue(Path(str(self.marker)+'.entered').exists())
            contender=os.open(self.lock,os.O_RDWR)
            with self.assertRaises(BlockingIOError): fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
            os.close(contender); out,err=p.communicate(timeout=5); self.assertEqual(p.returncode,0,err.decode())
            contender=os.open(self.lock,os.O_RDWR); fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB); os.close(contender)
        finally:
            if p.poll() is None: p.kill(); p.wait()

    def test_invalid_owner_fd_inode_symlink_or_lock_permissions_refuse_rotator(self):
        for kind in ('missing','wrong','symlink','unsafe'):
            self.marker.unlink(missing_ok=True); self.argv.unlink(missing_ok=True)
            fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
            env=os.environ|{"HOME":str(self.home),"XDG_RUNTIME_DIR":str(self.runtime),"PYTHONDONTWRITEBYTECODE":"1"}
            extra=()
            if kind=='wrong':
                other=os.open(self.home/'wrong',os.O_CREAT|os.O_RDWR,0o600); extra=(other,)
            if kind=='symlink': self.lock.rename(self.runtime/'real'); self.lock.symlink_to(self.runtime/'real')
            if kind=='unsafe': os.chmod(self.lock,0o666)
            p=subprocess.run([sys.executable,str(self.bin/'ezwallpaper-sddm-rotate.py')],env=env,pass_fds=extra if kind in ('missing','wrong') else (fd,),capture_output=True,timeout=5)
            self.assertNotEqual(p.returncode,0,kind); self.assertFalse(self.argv.exists(),kind); os.close(fd)
            if kind=='wrong': os.close(other)
            if kind=='symlink': self.lock.unlink(); (self.runtime/'real').rename(self.lock)
            if kind=='unsafe': os.chmod(self.lock,0o644)

    def test_timeout_kills_publisher_decoder_runs_cleanup_and_preserves_cache(self):
        pidfile=self.home/'pid'; cache=self.home/'cache'; cache.write_text('old-good')
        self.publisher.write_text("import pathlib,subprocess,time\n"
            f"PID={str(pidfile)!r}; MARK={str(self.marker)!r}\n"
            "def publish_after_owner_success():\n p=subprocess.Popen(['sleep','30']); pathlib.Path(PID).write_text(str(p.pid)); time.sleep(30)\n"
            "def cleanup_after_abort():\n pathlib.Path(MARK+'.cleanup').write_text('clean')\n")
        code=("import importlib.util; s=importlib.util.spec_from_file_location('w',%r); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.PUBLISH_TIMEOUT_SECONDS=.2; raise SystemExit(m.main())")%str(self.bin/'ezwallpaper-sddm-rotate.py')
        fd=os.open(self.lock,os.O_RDWR); fcntl.flock(fd,fcntl.LOCK_EX)
        env=os.environ|{"HOME":str(self.home),"XDG_RUNTIME_DIR":str(self.runtime),"PYTHONDONTWRITEBYTECODE":"1"}
        p=subprocess.run([sys.executable,'-c',code],env=env,pass_fds=(fd,),capture_output=True,timeout=5); os.close(fd)
        self.assertEqual(p.returncode,0); self.assertTrue(Path(str(self.marker)+'.cleanup').exists()); self.assertEqual(cache.read_text(),'old-good')
        with self.assertRaises(ProcessLookupError): os.kill(int(pidfile.read_text()),0)

if __name__=='__main__': unittest.main()
