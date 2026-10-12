"""One-shot SHA-256 baselines and change reports; no background service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def snapshot(root):
    root=Path(root).resolve(strict=True)
    if not root.is_dir(): raise ValueError('Root must be a directory')
    files={};errors=[];skipped=[]
    def onerror(exc):errors.append(str(exc))
    for directory,dirs,names in os.walk(root,followlinks=False,onerror=onerror):
        for name in list(dirs):
            path=Path(directory)/name
            if path.is_symlink():dirs.remove(name);skipped.append(str(path.relative_to(root)))
        for name in sorted(names):
            path=Path(directory)/name;relative=path.relative_to(root).as_posix()
            try:
                flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
                fd=os.open(path,flags)
                with os.fdopen(fd,'rb') as handle:
                    before=os.fstat(handle.fileno())
                    if not stat.S_ISREG(before.st_mode): skipped.append(relative);continue
                    digest=hashlib.sha256()
                    for block in iter(lambda:handle.read(65536),b''): digest.update(block)
                    after=os.fstat(handle.fileno())
                current=path.lstat()
                signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode)
                if signature(before)!=signature(after) or signature(after)!=signature(current):
                    errors.append(relative+': changed during scan');continue
                files[relative]=dict(sha256=digest.hexdigest(),size=after.st_size,mode=stat.S_IMODE(after.st_mode))
            except OSError as exc:
                if path.is_symlink():skipped.append(relative)
                else:errors.append(relative+': '+str(exc))
    return dict(schema=1,root=str(root),files=files,errors=errors,skipped=sorted(skipped))


def compare(old,new):
    if old.get('schema')!=1 or new.get('schema')!=1:raise ValueError('Unsupported baseline schema')
    if old['root']!=new['root']:raise ValueError('Baseline root mismatch')
    previous=old['files'];current=new['files']
    added=sorted(current.keys()-previous.keys())
    absent=sorted(previous.keys()-current.keys())
    uncertain=bool(new['errors'] or new['skipped'])
    return dict(added=added,removed=[] if uncertain else absent,unresolved_absences=absent if uncertain else [],
                modified=sorted(k for k in current.keys() & previous.keys() if current[k]!=previous[k]),
                errors=new['errors'],skipped=new['skipped'],complete=not uncertain,
                note='SHA-256, size and mode compared. Absences are not called deletions when coverage is incomplete.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['baseline','check'])
    p.add_argument('root',type=Path);p.add_argument('baseline',type=Path);args=p.parse_args()
    try:
        root=args.root.resolve(strict=True);baseline=args.baseline.resolve()
        if baseline==root or root in baseline.parents: raise ValueError('Store the baseline outside the watched directory')
        current=snapshot(root)
        if args.action=='baseline':
            if current['errors']:raise ValueError('Refusing baseline with collection errors: '+str(current['errors']))
            fd=os.open(baseline,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump(current,f,indent=2)
            print(json.dumps(dict(files=len(current['files']),skipped=current['skipped'])))
        else:
            result=compare(json.loads(baseline.read_text()),current);print(json.dumps(result,indent=2))
            return 2 if result['errors'] or result['unresolved_absences'] else int(bool(result['added'] or result['removed'] or result['modified']))
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
