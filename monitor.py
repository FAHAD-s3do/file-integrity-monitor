"""One-shot SHA-256 baselines and change reports; no background service."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat


def load_baseline(path):
    """Reject duplicate JSON members before baseline schema validation."""
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate baseline JSON key: ' + repr(key))
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def _relative_path(value, field):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError(f'{field} must contain canonical relative POSIX paths')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != value or value == '.':
        raise ValueError(f'{field} must contain canonical relative POSIX paths')


def validate_snapshot(value, label='Snapshot'):
    """Validate persisted snapshot data before it can influence a verdict."""
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be a JSON object')
    if value.get('schema') != 1:
        raise ValueError('Unsupported baseline schema')
    root = value.get('root')
    if not isinstance(root, str) or not root or not Path(root).is_absolute():
        raise ValueError(f'{label} root must be an absolute path')
    files = value.get('files')
    if not isinstance(files, dict):
        raise ValueError(f'{label} files must be an object')
    for relative, record in files.items():
        _relative_path(relative, f'{label} files')
        if not isinstance(record, dict):
            raise ValueError(f'{label} file records must be objects')
        digest = record.get('sha256')
        if (not isinstance(digest, str) or len(digest) != 64 or
                any(char not in '0123456789abcdef' for char in digest)):
            raise ValueError(f'{label} file sha256 must be 64 lowercase hexadecimal characters')
        size = record.get('size')
        mode = record.get('mode')
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f'{label} file size must be a non-negative integer')
        if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 0o7777:
            raise ValueError(f'{label} file mode must be an integer from 0 to 4095')
    for field in ('errors', 'skipped'):
        entries = value.get(field)
        if not isinstance(entries, list) or any(not isinstance(item, str) for item in entries):
            raise ValueError(f'{label} {field} must be a list of strings')
        if field == 'skipped':
            for entry in entries:
                _relative_path(entry, f'{label} skipped')
    return value


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
    validate_snapshot(old, 'Baseline')
    validate_snapshot(new, 'Current snapshot')
    if old['root']!=new['root']:raise ValueError('Baseline root mismatch')
    previous=old['files'];current=new['files']
    added=sorted(current.keys()-previous.keys())
    absent=sorted(previous.keys()-current.keys())
    uncertain=bool(new['errors'] or new['skipped'])
    baseline_complete=not bool(old['errors'] or old['skipped'])
    return dict(added=added,removed=[] if uncertain else absent,unresolved_absences=absent if uncertain else [],
                modified=sorted(k for k in current.keys() & previous.keys() if current[k]!=previous[k]),
                errors=new['errors'],skipped=new['skipped'],
                baseline_errors=old['errors'],baseline_skipped=old['skipped'],
                baseline_complete=baseline_complete,current_complete=not uncertain,
                complete=baseline_complete and not uncertain,
                note='SHA-256, size and mode compared. Absences are not called deletions when current coverage is incomplete. Added means absent from the recorded baseline, not necessarily newly created; baseline gaps may predate this check.')


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
            result=compare(load_baseline(baseline),current);print(json.dumps(result,indent=2))
            return 2 if not result['complete'] else int(bool(result['added'] or result['removed'] or result['modified']))
    except (OSError,ValueError,KeyError,TypeError) as exc:p.exit(2,str(exc)+'\n')
    return 0
if __name__=='__main__':raise SystemExit(main())

