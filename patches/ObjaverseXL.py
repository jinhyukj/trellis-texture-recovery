import os
import re
import json
import urllib.parse
import shutil
import argparse
import tempfile
import zipfile
import hashlib
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import pandas as pd
import objaverse.xl as oxl
from utils import get_file_hash


def add_args(parser: argparse.ArgumentParser):
    parser.add_argument('--source', type=str, default='sketchfab',
                        help='Data source to download annotations from (github, sketchfab)')


def get_metadata(source, **kwargs):
    if source == 'sketchfab':
        metadata = pd.read_csv("hf://datasets/JeffreyXiang/TRELLIS-500K/ObjaverseXL_sketchfab.csv")
    elif source == 'github':
        metadata = pd.read_csv("hf://datasets/JeffreyXiang/TRELLIS-500K/ObjaverseXL_github.csv")
    else:
        raise ValueError(f"Invalid source: {source}")
    return metadata


# ─────────────────────────────────────────────────────────────────────────────
# 2026-08-26 B'-strict extract mode for the github source (zip-less):
#   clone(temp) → sha-verified callback → copy matched file + referenced deps
#   into raw/github/extracted/<org>/<repo>/<inner-path> → temp discarded.
#   Resume is file-level: rows whose extracted file already exists are skipped;
#   permanently missing/modified fileIdentifiers are memorised in text files.
# ─────────────────────────────────────────────────────────────────────────────

_TEXRE = re.compile(rb'[\w\-. \\/:]{1,200}\.(?:png|jpg|jpeg|tga|bmp|tif|tiff|dds|exr|hdr|webp|psd)', re.I)

def _bp_refs(repo_root, inner):
    """B'-strict: return repo-relative paths referenced by the matched file."""
    refs = set()
    src = os.path.join(repo_root, inner)
    ext = inner.rsplit('.', 1)[-1].lower() if '.' in inner else ''
    # basename index of the repo (lazy, small repos → cheap)
    index = {}
    for dp, _, fs in os.walk(repo_root):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), repo_root)
            index.setdefault(f.lower(), []).append(rel)
    def by_base(name):
        return index.get(os.path.basename(name.replace('\\', '/')).strip().lower(), [])
    try:
        if ext == 'obj':
            txt = open(src, 'rb').read().decode('utf8', 'ignore')
            for mtl in re.findall(r'(?im)^mtllib\s+(.+)$', txt):
                for x in by_base(mtl):
                    refs.add(x)
                    mt = open(os.path.join(repo_root, x), 'rb').read().decode('utf8', 'ignore')
                    for tex in re.findall(r'(?im)^map_\w+\s+(.+)$', mt):
                        refs.update(by_base(tex.split()[-1]))
        elif ext == 'gltf':
            g = json.loads(open(src, 'rb').read())
            for sec in ('buffers', 'images'):
                for it in g.get(sec, []):
                    u = it.get('uri', '')
                    if u and not u.startswith('data:'):
                        refs.update(by_base(u))
        elif ext == 'dae':
            txt = open(src, 'rb').read().decode('utf8', 'ignore')
            for tex in re.findall(r'<init_from>([^<]+)</init_from>', txt):
                refs.update(by_base(tex))
        elif ext in ('fbx', 'blend'):
            data = open(src, 'rb').read()
            for m in _TEXRE.findall(data):
                refs.update(by_base(m.decode('utf8', 'ignore')))
    except Exception:
        pass
    return refs


def _atomic_copy(src, dst):
    if os.path.exists(dst) or not os.path.exists(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.copytmp'
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def _split_fid(file_identifier):
    parts = file_identifier.split('/')
    return parts[3], parts[4], '/'.join(parts[7:])   # org, repo, inner


def _gh_found(local_path=None, file_identifier=None, sha256=None, metadata=None, **kw):
    out_root = os.environ['GH_EXTRACT_ROOT']
    org, repo, inner = _split_fid(file_identifier)
    lp = local_path.replace('\\', '/')
    if not lp.endswith(inner):
        # path mismatch (rare) — fall back to copying just the file flat
        dst = os.path.join(out_root, 'extracted', org, repo, inner)
        _atomic_copy(local_path, dst)
        return
    repo_root = lp[:-len(inner)].rstrip('/')
    dest_root = os.path.join(out_root, 'extracted', org, repo)
    # refs FIRST, matched mesh LAST: the mesh file doubles as the "set complete"
    # marker, so a kill between copies can never strand a mesh without its refs
    for rel in _bp_refs(repo_root, inner):
        _atomic_copy(os.path.join(repo_root, rel), os.path.join(dest_root, rel))
    _atomic_copy(os.path.join(repo_root, inner), os.path.join(dest_root, inner))


def _append_line(path, line):
    with open(path, 'a') as f:
        f.write(line + '\n')


def _gh_missing(file_identifier=None, **kw):
    _append_line(os.path.join(os.environ['GH_EXTRACT_ROOT'], 'missing_fids.txt'), file_identifier)


def _gh_modified(file_identifier=None, new_sha256=None, old_sha256=None, **kw):
    _append_line(os.path.join(os.environ['GH_EXTRACT_ROOT'], 'modified_fids.txt'), file_identifier)


def download(metadata, output_dir, **kwargs):
    os.makedirs(os.path.join(output_dir, 'raw'), exist_ok=True)

    is_github = metadata['file_identifier'].str.contains('github.com', regex=False).mean() > 0.5

    if not is_github:
        # ── sketchfab: original zip-free per-file behaviour (unchanged) ──
        annotations = oxl.get_annotations()
        annotations = annotations[annotations['sha256'].isin(metadata['sha256'].values)]
        file_paths = oxl.download_objects(
            annotations,
            download_dir=os.path.join(output_dir, "raw"),
            save_repo_format="zip",
            processes=int(os.environ.get("OXL_PROCESSES", "16")),
        )
        downloaded = {}
        md = metadata.set_index("file_identifier")
        for k, v in file_paths.items():
            downloaded[md.loc[k, "sha256"]] = os.path.relpath(v, output_dir)
        return pd.DataFrame(downloaded.items(), columns=['sha256', 'local_path'])

    # ── github: B'-strict extract mode ──
    raw = os.path.join(output_dir, 'raw', 'github')
    os.environ['GH_EXTRACT_ROOT'] = raw
    os.makedirs(os.path.join(raw, 'extracted'), exist_ok=True)

    md = metadata.copy()
    parts = md['file_identifier'].str.split('/')
    md['org'] = parts.str[3]; md['repo'] = parts.str[4]
    md['inner'] = parts.str[7:].str.join('/')
    md['relpath'] = 'raw/github/extracted/' + md['org'] + '/' + md['repo'] + '/' + md['inner']

    # file-level resume: skip rows whose extracted file already exists,
    # and rows recorded as permanently missing/modified
    skip_fids = set()
    for fn in ('missing_fids.txt', 'modified_fids.txt'):
        p = os.path.join(raw, fn)
        if os.path.exists(p):
            skip_fids |= set(l.strip() for l in open(p) if l.strip())
    exists_mask = md['relpath'].apply(lambda r: os.path.exists(os.path.join(output_dir, r)))
    todo = md[~exists_mask & ~md['file_identifier'].isin(skip_fids)]
    print(f'[extract-mode] total {len(md)} | already extracted {int(exists_mask.sum())} | '
          f'skip(missing/modified) {len(md)-int(exists_mask.sum())-len(todo)} | to download {len(todo)}')

    if len(todo) > 0:
        annotations = oxl.get_annotations()
        annotations = annotations[annotations['sha256'].isin(todo['sha256'].values)]
        oxl.download_objects(
            annotations,
            download_dir=None,
            save_repo_format=None,
            processes=int(os.environ.get("OXL_PROCESSES", "16")),
            handle_found_object=_gh_found,
            handle_missing_object=_gh_missing,
            handle_modified_object=_gh_modified,
        )

    # records = rows whose extracted file now exists (sha was verified by
    # objaverse before the callback copied it; copies are atomic)
    exists_mask = md['relpath'].apply(lambda r: os.path.exists(os.path.join(output_dir, r)))
    done = md[exists_mask]
    print(f'[extract-mode] recorded {len(done)} objects')
    return pd.DataFrame({'sha256': done['sha256'].values, 'local_path': done['relpath'].values})


def foreach_instance(metadata, output_dir, func, max_workers=None, desc='Processing objects', no_file=False):
    records = []
    if max_workers is None or max_workers <= 0:
        max_workers = os.cpu_count()
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor, \
            tqdm(total=len(metadata), desc=desc) as pbar:
            def worker(metadatum):
                try:
                    sha256 = metadatum['sha256']
                    if no_file:
                        record = func(None, metadatum)
                    else:
                        local_path = metadatum['local_path']
                        if local_path.startswith('raw/github/repos/'):
                            path_parts = local_path.split('/')
                            file_name = os.path.join(*path_parts[5:])
                            zip_file = os.path.join(output_dir, *path_parts[:5])
                            with tempfile.TemporaryDirectory() as tmp_dir:
                                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                                    zip_ref.extractall(tmp_dir)
                                file = os.path.join(tmp_dir, file_name)
                                record = func(file, metadatum)
                        else:
                            file = os.path.join(output_dir, local_path)
                            record = func(file, metadatum)
                    if record is not None:
                        records.append(record)
                    pbar.update()
                except Exception as e:
                    print(f"Error processing object {metadatum.get('sha256', 'unknown')}: {e}")
                    pbar.update()
            for metadatum in metadata.to_dict('records'):
                executor.submit(worker, metadatum)
            executor.shutdown(wait=True)
    except Exception as e:
        print(f"Error happened during processing: {e}")
    return pd.DataFrame.from_records(records)
