#!/usr/bin/env python3
"""
generate_isce2_configs_from_csv.py

Generate ISCE2 topsApp.xml configuration files from CSV pair lists.

Usage:
    python3 generate_isce2_configs_from_csv.py \
        --csv sbas_pairs_2023.csv \
        --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \
        --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas \
        [--dry_run]
"""

import os
import pandas as pd
from pathlib import Path
import argparse
from datetime import datetime


def generate_topsApp_xml(reference_zip, secondary_zip, output_path, dem_path=None, orbit_dir=None, enable_dense_offsets=True):
    """
    Generate ISCE2 topsApp.xml configuration file for interferometric pair.
    
    Args:
        reference_zip: Full path to reference (master) .zip file
        secondary_zip: Full path to secondary (slave) .zip file
        output_path: Where to save the XML file
        dem_path: Optional DEM file path (ISCE2 can auto-download if None)
        orbit_dir: Optional orbit directory (ISCE2 can auto-download if None)
    """
    # Get the directory where the XML file will be saved (for output)
    config_dir = os.path.dirname(output_path)
    
    dense_offsets_block = ""
    if enable_dense_offsets:
        dense_offsets_block = """
    <!-- Enable dense offsets and dense-offset geocoding -->
    <property name=\"do dense offsets\">True</property>
"""

    # ISCE2 topsApp.xml format - with output directories specified
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<topsApp>
  <component name="topsinsar">
    <property name="Sensor name">SENTINEL1</property>
    <component name="reference">
        <property name="safe">{reference_zip}</property>
        <property name="output directory">{config_dir}/reference</property>
    </component>
    <component name="secondary">
        <property name="safe">{secondary_zip}</property>
        <property name="output directory">{config_dir}/secondary</property>
    </component>
    
    <!-- Process all three subswaths -->
    <property name="swaths">[1, 2, 3]</property>
    
    <!-- Enable phase unwrapping -->
    <property name="do unwrap">True</property>
    <property name="unwrapper name">snaphu_mcf</property>
    
    <!-- Multilooking for better SNR -->
    <property name="azimuth looks">7</property>
    <property name="range looks">19</property>
    
    <!-- Filtering strength (0.0 to 1.0) -->
    <property name="filter strength">0.5</property>
{dense_offsets_block}
  </component>
</topsApp>
"""
    
    with open(output_path, 'w') as f:
        f.write(content)


def find_safe_file(data_path, granule_name):
    """
    Find .zip or .SAFE file matching granule name.
    
    Args:
        data_path: Directory containing SAFE files
        granule_name: Granule name (without .SAFE or .zip extension)
    
    Returns:
        Full path to file if found, None otherwise
    """
    data_path = Path(data_path)
    
    # Try .zip files first (most common)
    zip_pattern = f"{granule_name}.zip"
    zip_matches = list(data_path.glob(zip_pattern))
    if zip_matches:
        return str(zip_matches[0])
    
    # Try .SAFE directories
    safe_pattern = f"{granule_name}.SAFE"
    safe_matches = list(data_path.glob(safe_pattern))
    if safe_matches:
        return str(safe_matches[0])
    
    # Try without extension (might be symlink)
    direct_matches = list(data_path.glob(granule_name))
    if direct_matches:
        return str(direct_matches[0])
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Generate ISCE2 topsApp.xml files from CSV pair list',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # SBAS pairs
  python3 generate_isce2_configs_from_csv.py \\
      --csv sbas_pairs_2023.csv \\
      --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \\
      --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas
  
  # PS pairs
  python3 generate_isce2_configs_from_csv.py \\
      --csv ps_pairs_2023.csv \\
      --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \\
      --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/ps
  
  # Dry run to check without creating files
  python3 generate_isce2_configs_from_csv.py \\
      --csv sbas_pairs_2023.csv \\
      --data_path /mnt/data/sbas_vs_ps_test_bologna/data/safe \\
      --output_dir /mnt/data/sbas_vs_ps_test_bologna/configs/sbas \\
      --dry_run
        """
    )
    
    parser.add_argument('--csv', required=True, 
                        help='CSV file with pairs (columns: master, slave, master_date, slave_date, path)')
    parser.add_argument('--data_path', required=True, 
                        help='Directory containing .zip or .SAFE files')
    parser.add_argument('--output_dir', required=True, 
                        help='Output directory for XML configuration files')
    parser.add_argument('--orbit_dir', default=None,
                        help='Optional directory with precise orbit files (ISCE2 auto-downloads if not provided)')
    parser.add_argument('--no_dense_offsets', action='store_true',
                        help='Disable dense offset estimation/geocoding in generated topsApp.xml')
    parser.add_argument('--dry_run', action='store_true',
                        help='Show what would be created without actually creating files')
    
    args = parser.parse_args()
    
    # Read pairs CSV
    print(f"📖 Reading pairs from: {args.csv}")
    try:
        df = pd.read_csv(args.csv)
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return 1
    
    # Verify required columns
    required_cols = ['master', 'slave', 'master_date', 'slave_date']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing required columns: {missing_cols}")
        print(f"   Available columns: {list(df.columns)}")
        return 1
    
    print(f"✅ Found {len(df)} pairs")
    print(f"   Columns: {list(df.columns)}")
    print()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created output directory: {output_dir}")
    else:
        print(f"🔍 DRY RUN: Would create output directory: {output_dir}")
    print()
    
    # Process each pair
    valid_pairs = []
    missing_files = []
    
    print("🔄 Processing pairs...")
    print("-" * 80)
    
    for idx, row in df.iterrows():
        master = row['master']
        slave = row['slave']
        master_date = row['master_date']
        slave_date = row['slave_date']
        
        # Find SAFE files
        master_path = find_safe_file(args.data_path, master)
        slave_path = find_safe_file(args.data_path, slave)
        
        if master_path and slave_path:
            # Create pair directory name from dates
            pair_name = f"{master_date}_{slave_date}"
            pair_dir = output_dir / pair_name
            xml_file = pair_dir / "topsApp.xml"
            
            if args.dry_run:
                print(f"✓ [{idx+1:3d}/{len(df)}] {pair_name}")
                print(f"           Would create: {xml_file}")
            else:
                # Create pair directory
                pair_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate XML
                generate_topsApp_xml(
                    reference_zip=master_path,
                    secondary_zip=slave_path,
                    output_path=str(xml_file),
                    orbit_dir=args.orbit_dir,
                    enable_dense_offsets=not args.no_dense_offsets,
                )
                
                print(f"✅ [{idx+1:3d}/{len(df)}] {pair_name} → {xml_file}")
            
            valid_pairs.append({
                'master': master,
                'slave': slave,
                'master_date': master_date,
                'slave_date': slave_date,
                'master_path': master_path,
                'slave_path': slave_path,
                'xml_file': str(xml_file)
            })
        else:
            print(f"⚠️  [{idx+1:3d}/{len(df)}] {master_date}_{slave_date} - Missing files:")
            if not master_path:
                print(f"           Master: {master}")
            if not slave_path:
                print(f"           Slave:  {slave}")
            
            missing_files.append({
                'master': master,
                'slave': slave,
                'master_date': master_date,
                'slave_date': slave_date,
                'master_found': master_path is not None,
                'slave_found': slave_path is not None
            })
    
    print("-" * 80)
    print()
    
    # Summary
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total pairs:        {len(df)}")
    print(f"Valid configs:      {len(valid_pairs)} ✅")
    print(f"Missing files:      {len(missing_files)} ⚠️")
    print()
    
    if not args.dry_run:
        # Save valid pairs list
        valid_csv = output_dir / "valid_pairs.csv"
        pd.DataFrame(valid_pairs).to_csv(valid_csv, index=False)
        print(f"✅ Saved valid pairs list: {valid_csv}")
        
        # Save missing files list
        if missing_files:
            missing_csv = output_dir / "missing_files.csv"
            pd.DataFrame(missing_files).to_csv(missing_csv, index=False)
            print(f"⚠️  Saved missing files list: {missing_csv}")
        
        print()
        print("✅ Configuration generation complete!")
        print()
        print("Next steps:")
        print("  1. Review generated XML files")
        print("  2. Run ISCE2 topsApp.py for each configuration")
        print("  3. Or use batch processing with Docker:")
        print(f"     cd /home/ubuntu/work/isce2-playbook")
        print(f"     ls {output_dir}/*/topsApp.xml | \\")
        print(f"       xargs -n 1 -P 4 -I {{}} docker compose run --rm isce2-insar topsApp.py {{}}")
    else:
        print("🔍 DRY RUN complete - no files created")
        print(f"   Run without --dry_run to generate {len(valid_pairs)} XML configurations")
    
    return 0


if __name__ == "__main__":
    exit(main())
