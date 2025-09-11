import h5py
import sys

def inspect_h5_structure(file_path):
    """
    Inspect the structure of an HDF5 file and print all datasets and groups.
    
    Args:
        file_path (str): Path to the HDF5 file to inspect.
    """
    try:
        with h5py.File(file_path, "r") as f:
            print(f"Inspecting HDF5 file: {file_path}\n")
            print(f"{'Path':<40} {'Type':<20} {'Shape':<20}")
            print("-" * 80)
            def print_structure(name, obj):
                obj_type = "Group" if isinstance(obj, h5py.Group) else "Dataset"
                shape = obj.shape if isinstance(obj, h5py.Dataset) else "N/A"
                print(f"{name:<40} {obj_type:<20} {shape}")
            f.visititems(print_structure)
    except Exception as e:
        print(f"Error inspecting file {file_path}: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python inspect_h5_structure.py <path_to_hdf5_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    inspect_h5_structure(file_path)

if __name__ == "__main__":
    main()
