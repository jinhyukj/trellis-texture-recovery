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
    metadata = pd.read_csv("hf://datasets/JeffreyXiang/TRELLIS-500K/3D-FUTURE.csv")
    return metadata
        

def download(metadata, output_dir, **kwargs):    
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(os.path.join(output_dir, 'raw', '3D-FUTURE-model.zip')):
        print("\033[93m")
        print("3D-FUTURE have to be downloaded manually")
        print(f"Please download the 3D-FUTURE-model.zip file and place it in the {output_dir}/raw directory")
        print("Visit https://tianchi.aliyun.com/specials/promotion/alibaba-3d-future for more information")
        print("\033[0m")
        raise FileNotFoundError("3D-FUTURE-model.zip not found")
    
    downloaded = {}
    metadata = metadata.set_index("file_identifier")
    with zipfile.ZipFile(os.path.join(output_dir, 'raw', '3D-FUTURE-model.zip')) as zip_ref:
        all_names = zip_ref.namelist()
        instances = [instance[:-1] for instance in all_names if re.match(r"^3D-FUTURE-model/[^/]+/$", instance)]
        instances = list(filter(lambda x: x in metadata.index, instances))
        
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor, \
            tqdm(total=len(instances), desc="Extracting") as pbar:
            def worker(instance: str) -> str:
                try:
                    instance_files = list(filter(lambda x: x.startswith(f"{instance}/") and not x.endswith("/"), all_names))
                    zip_ref.extractall(os.path.join(output_dir, 'raw'), members=instance_files)
                    sha256 = get_file_hash(os.path.join(output_dir, 'raw', f"{instance}/image.jpg"))
                    pbar.update()
                    return sha256
                except Exception as e:
                    pbar.update()
                    print(f"Error extracting for {instance}: {e}")
                    return None
                
            sha256s = executor.map(worker, instances)
            executor.shutdown(wait=True)

    for k, sha256 in zip(instances, sha256s):
        if sha256 is not None:
            if sha256 == metadata.loc[k, "sha256"]:
                downloaded[sha256] = os.path.join("raw", f"{k}/raw_model.obj")
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
