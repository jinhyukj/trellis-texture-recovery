import os
import re
import argparse
import zipfile
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import pandas as pd
from utils import get_file_hash


def add_args(parser: argparse.ArgumentParser):
    pass


def get_metadata(**kwargs):
    metadata = pd.read_csv("hf://datasets/JeffreyXiang/TRELLIS-500K/Toys4k.csv")
    return metadata
        

def download(metadata, output_dir, **kwargs):    
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(os.path.join(output_dir, 'raw', 'toys4k_blend_files.zip')):
        print("\033[93m")
        print("Toys4k have to be downloaded manually")
        print(f"Please download the toys4k_blend_files.zip file and place it in the {output_dir}/raw directory")
        print("Visit https://github.com/rehg-lab/lowshot-shapebias/tree/main/toys4k for more information")
        print("\033[0m")
        raise FileNotFoundError("toys4k_blend_files.zip not found")
    
    downloaded = {}
    metadata = metadata.set_index("file_identifier")
    with zipfile.ZipFile(os.path.join(output_dir, 'raw', 'toys4k_blend_files.zip')) as zip_ref:
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor, \
            tqdm(total=len(metadata), desc="Extracting") as pbar:
            def worker(instance: str) -> str:
                try:
                    zip_ref.extract(os.path.join('toys4k_blend_files', instance), os.path.join(output_dir, 'raw'))
                    sha256 = get_file_hash(os.path.join(output_dir, 'raw/toys4k_blend_files', instance))
                    pbar.update()
                    return sha256
                except Exception as e:
                    pbar.update()
                    print(f"Error extracting for {instance}: {e}")
                    return None
                
            sha256s = executor.map(worker, metadata.index)
            executor.shutdown(wait=True)

    for k, sha256 in zip(metadata.index, sha256s):
        if sha256 is not None:
            if sha256 == metadata.loc[k, "sha256"]:
                downloaded[sha256] = os.path.join("raw/toys4k_blend_files", k)
            else:
                print(f"Error downloading {k}: sha256s do not match")

    return pd.DataFrame(downloaded.items(), columns=['sha256', 'local_path'])


def foreach_instance(metadata, output_dir, func, max_workers=None, desc='Processing objects', no_file=False) -> pd.DataFrame:
    # Ported from microsoft/TRELLIS dataset_toolkits/datasets (2026-08-22) for TRELLIS.2 data_toolkit.
    # Only change vs. original: callback receives (file, metadatum) -- TRELLIS.2 convention,
    # same as PR #116 ObjaverseXL.py -- instead of (file, sha256); `no_file` option added.
    records = []
    if max_workers is None or max_workers <= 0:
        max_workers = os.cpu_count()
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor, \
            tqdm(total=len(metadata), desc=desc) as pbar:
            def worker(metadatum):
                try:
                    if no_file:
                        record = func(None, metadatum)
                    else:
                        file = os.path.join(output_dir, metadatum['local_path'])
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
