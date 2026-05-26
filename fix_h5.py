import h5py
import json

def strip_quantization_config(filepath):
    print(f"Opening {filepath}...")
    with h5py.File(filepath, 'r+') as f:
        if 'model_config' in f.attrs:
            config_str = f.attrs['model_config']
            if isinstance(config_str, bytes):
                config_str = config_str.decode('utf-8')
            
            config = json.loads(config_str)
            
            # Recursively find and delete quantization_config
            def clean_dict(d):
                if isinstance(d, dict):
                    if 'quantization_config' in d:
                        del d['quantization_config']
                    for k, v in d.items():
                        clean_dict(v)
                elif isinstance(d, list):
                    for item in d:
                        clean_dict(item)
                        
            clean_dict(config)
            
            # Save it back
            new_config_str = json.dumps(config)
            f.attrs['model_config'] = new_config_str.encode('utf-8')
            print("Successfully stripped all quantization_config parameters from the HDF5 file!")
        else:
            print("No model_config found in attributes.")

strip_quantization_config("model/model.h5")
