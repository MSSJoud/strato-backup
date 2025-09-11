"""
generate_topsApp_batch.py

Author:
Date:

Description:
    Generate ISCE2 topsApp.xml files from Sentinel-1 pairs selected from PostgreSQL database.

Usage:
    python generate_topsApp_batch.py --db_name aoi_3_slcs --table_name slc_data --data_path /mnt/slc_data --output_dir ./isce2_xmls --bmax 200 --tmax 300 [--dry_run] [--plot]
"""

import os
import pandas as pd
from pathlib import Path
import argparse
from datetime import datetime
from logger import log_script_arguments
import matplotlib.pyplot as plt
from select_s1_pairs_from_postgres import select_s1_pairs_from_db


def generate_topsApp_xml(reference_zip, secondary_zip, output_path):
    content = f"""<topsApp>
    <component name="topsinsar">
        <property name="Sensor name">SENTINEL1</property>
        <property name="Sentinel1 ZIP file">[{reference_zip}, {secondary_zip}]</property>
        <property name="Swaths">[IW1, IW2, IW3]</property>
        <property name="Polarizations">['VV']</property>
        <property name="Processing mode">full</property>
        <component name="Reference"><property name="safe">{reference_zip}</property></component>
        <component name="Secondary"><property name="safe">{secondary_zip}</property></component>
    </component>
</topsApp>
"""
    with open(output_path, 'w') as f:
        f.write(content)


def plot_pairs(all_df, valid_df, out_dir, show=False):
    def extract_year_and_bperp(df):
        years = []
        bperp = df['Bperp'].astype(float).tolist()
        for master in df['master']:
            try:
                date_str = master.split('_')[5][:8]
                date = datetime.strptime(date_str, "%Y%m%d")
                year_decimal = date.year + date.timetuple().tm_yday / 365.0
                years.append(year_decimal)
            except:
                years.append(None)
        return years, bperp

    # All
    all_years, all_bp = extract_year_and_bperp(all_df)
    df_all = pd.DataFrame({'year': all_years, 'bperp': all_bp}).dropna()
    df_all.to_csv(os.path.join(out_dir, 'all_pairs_for_plot.csv'), index=False)
    plt.figure()
    plt.scatter(df_all['year'], df_all['bperp'], c='lightgray')
    plt.title("All Pairs")
    plt.xlabel("Acquisition Year")
    plt.ylabel("B⊥ (m)")
    plt.savefig(os.path.join(out_dir, "all_pairs_plot.png"))
    print(f"[✓] Saved CSV: {os.path.join(out_dir, 'all_pairs_for_plot.csv')}")
    print(f"[✓] Saved plot: {os.path.join(out_dir, 'all_pairs_plot.png')}")

    if show: plt.show()
    plt.close()

    # Valid
    val_years, val_bp = extract_year_and_bperp(valid_df)
    df_val = pd.DataFrame({'year': val_years, 'bperp': val_bp}).dropna()
    df_val.to_csv(os.path.join(out_dir, 'valid_pairs_for_plot.csv'), index=False)
    plt.figure()
    plt.scatter(df_val['year'], df_val['bperp'], c='black')
    plt.title("Valid Pairs (Zips found)")
    plt.xlabel("Acquisition Year")
    plt.ylabel("B⊥ (m)")
    plt.savefig(os.path.join(out_dir, "valid_pairs_plot.png"))
    print(f"[✓] Saved CSV: {os.path.join(out_dir, 'valid_pairs_for_plot.csv')}")
    print(f"[✓] Saved plot: {os.path.join(out_dir, 'valid_pairs_plot.png')}")

    if show: plt.show()
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db_name', default='aoi_3_slcs', help='PostgreSQL DB name')
    parser.add_argument('--table_name', default='slc_data', help='Table in PostgreSQL')
    parser.add_argument('--data_path', required=True, help='Path to zipped .SAFE files')
    parser.add_argument('--output_dir', default='./isce2_xmls', help='Output XML directory')
    parser.add_argument('--bmax', type=float, default=200.0, help='Max B⊥ in meters')
    parser.add_argument('--tmax', type=int, default=300, help='Max temporal separation (days)')
    parser.add_argument('--dry_run', action='store_true')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    pairs_df = select_s1_pairs_from_db(args.db_name, args.table_name, args.bmax, args.tmax)

    valid = []
    missing = []

    for _, row in pairs_df.iterrows():
        master, slave, path_str = row['master'], row['slave'], str(row['path'])
        path_dir = Path(args.data_path) / f"path_{path_str}"
        ref_zip = list(path_dir.glob(f'*{master}*.zip'))
        sec_zip = list(path_dir.glob(f'*{slave}*.zip'))

        if ref_zip and sec_zip:
            xml_dir = Path(args.output_dir) / f"path_{path_str}"
            os.makedirs(xml_dir, exist_ok=True)
            xml_file = xml_dir / f"{master}_{slave}_topsApp.xml"
            if args.dry_run:
                print(f"\u2611 DRY_RUN: Would create {xml_file}")
            else: 
                generate_topsApp_xml(str(ref_zip[0]), str(sec_zip[0]), xml_file)
                print(f"\u2705 XML ready: {xml_file}")
            valid.append(row)
        else:
            print(f"\u26A0 Missing: {master} or {slave} in {path_dir}")
            missing.append(row)

    pd.DataFrame(valid).to_csv(os.path.join(args.output_dir, 'valid_pairs.csv'), index=False)
    print(f"[✓] Saved CSV: {os.path.join(args.output_dir, 'valid_pairs.csv')}")

    pd.DataFrame(missing).to_csv(os.path.join(args.output_dir, 'missing_pairs.csv'), index=False)
    print(f"[✓] Saved CSV: {os.path.join(args.output_dir, 'missing_pairs.csv')}")

    log_script_arguments(
        script_name="generate_topsApp_batch.py",
        arguments_dict=vars(args),
        descriptions_dict={
            'db_name': 'PostgreSQL DB',
            'table_name': 'DB table',
            'data_path': 'Directory of .zip files',
            'output_dir': 'Where to save XMLs',
            'bmax': 'Max B⊥',
            'tmax': 'Max ΔT',
            'dry_run': 'Simulate only',
            'plot': 'Show plot'
        }
    )

    # Plotting
    if args.plot: 
        valid_df = pd.DataFrame(valid)
        plot_pairs(pairs_df, valid_df, args.output_dir, show=args.plot)
    

if __name__ == "__main__":
    main()
