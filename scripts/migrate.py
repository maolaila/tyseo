"""Encrypted portable archives; the decryption key never belongs to the Git repository."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
from Crypto.Cipher import AES

ROOT=Path(__file__).resolve().parents[1]
CHUNK=25*1024*1024

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()

def pack(key_path, business, extra=None):
    key_path=Path(key_path).resolve()
    if key_path.is_relative_to(ROOT):raise ValueError('Keep migration key outside Git workspace')
    key_path.parent.mkdir(parents=True,exist_ok=True)
    if not key_path.exists():
        with key_path.open('xb') as f:f.write(os.urandom(32))
    key=key_path.read_bytes()
    if len(key)!=32:raise ValueError('Key must contain 32 bytes')
    target=ROOT/'migration'/('bundle-'+__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S'))
    target.mkdir(parents=True,exist_ok=False)
    files=[]
    for directory in ('runs','drafts','catalog','fixtures'):
        for p in (ROOT/directory).rglob('*'):
            if not p.is_file() or any(x in p.parts for x in ('__pycache__','.playwright-cli','.playwright','browser-profile')):continue
            files.append((p,p.relative_to(ROOT).as_posix()))
    # Explicit project configuration and local requirements, not company source or unrelated browser credentials.
    business=Path(business)
    for p in [business/'.env',business/'AGENTS.md',business/'LOCAL_MAINTENANCE.md',*list((business/'.local-records').rglob('*'))]:
        if p.is_file():files.append((p,'private/business/'+p.relative_to(business).as_posix()))
    # User requested all tySEO data outside business code, including sensitive runtime data.
    for p in (business.parent/'local_cache').rglob('*'):
        if p.is_file():files.append((p,'private/local_cache/'+p.relative_to(business.parent/'local_cache').as_posix()))
    for p in business.parent.glob('*.log'):
        if p.is_file():files.append((p,'private/runtime-logs/'+p.name))
    with tempfile.TemporaryDirectory(prefix='tyseo-pack-') as temp:
        archive=Path(temp)/'payload.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p,name in files:z.write(p,name)
            for name,value in (extra or {}).items():z.writestr(name,value)
        cipher=AES.new(key,AES.MODE_GCM)
        manifest={'format':'tyseo-aes256-gcm-zip-v1','nonce':cipher.nonce.hex(),'parts':[],'files':len(files)+len(extra or {}),'key_in_repository':False}
        with archive.open('rb') as source:
            index=0
            while True:
                data=source.read(CHUNK)
                if not data:break
                name=f'payload.{index:03d}.enc';p=target/name;p.write_bytes(cipher.encrypt(data))
                manifest['parts'].append({'file':name,'sha256':file_hash(p),'bytes':p.stat().st_size});index+=1
        manifest['tag']=cipher.digest().hex()
        (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (ROOT/'migration/latest.json').write_text(json.dumps({'bundle':target.name},indent=2),encoding='utf-8')
    return {'bundle':target.name,'files':manifest['files'],'encrypted_bytes':sum(x['bytes'] for x in manifest['parts']),'parts':len(manifest['parts'])}

def restore(key_path,destination):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    bundle=ROOT/'migration'/json.loads((ROOT/'migration/latest.json').read_text())['bundle']
    manifest=json.loads((bundle/'manifest.json').read_text())
    cipher=AES.new(Path(key_path).read_bytes(),AES.MODE_GCM,nonce=bytes.fromhex(manifest['nonce']))
    with tempfile.TemporaryDirectory(prefix='tyseo-restore-') as temp:
        archive=Path(temp)/'payload.zip'
        with archive.open('wb') as f:
            for part in manifest['parts']:
                p=bundle/part['file']
                if p.parent!=bundle or file_hash(p)!=part['sha256']:raise ValueError('Invalid archive part')
                f.write(cipher.decrypt(p.read_bytes()))
        cipher.verify(bytes.fromhex(manifest['tag'])) # Authenticate before extracting any plaintext.
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                path=(destination/item.filename).resolve()
                if not path.is_relative_to(destination) or path.exists():raise ValueError('Unsafe archive path or existing destination file')
            z.extractall(destination)
    return {'restored_to':str(destination),'files':manifest['files']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','restore']);p.add_argument('--key-file',required=True)
    p.add_argument('--business-repo');p.add_argument('--destination')
    a=p.parse_args()
    print(json.dumps(pack(a.key_file,a.business_repo) if a.action=='pack' else restore(a.key_file,a.destination)))
