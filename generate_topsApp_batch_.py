"""
generate_topsApp_batch.py

Author: 
Date: 

Description:
    Generate ISCE2 topsApp.xml files from Sentinel-1 interferometric pairs.
    Expects a CSV with columns: master, slave, path, delta_days

Usage:
    python generate_topsApp_batch.py --pairs sel_pairs.csv --data_path /mnt/slc_data --output_dir ./isce2_xmls [--dry_run] [--plot]
"""

import os
import pandas as pd
from pathlib import Path
import argparse
import matplotlib.pyplot as plt
from datetime import datetime
from logger import log_script_arguments

def generate_topsApp_xml(reference_zip, secondary_zip, output_path):
    content = f"""<topsApp>
    <component name="topsinsar">

        <property name="Sensor name">SENTINEL1</property>
        <property name="Sentinel1 ZIP file">[{reference_zip}, {secondary_zip}]</property>
        <property name="Swaths">[IW1, IW2, IW3]</property>
        <property name="Polarizations">['VV']</property>
        <property name="Processing mode">full</property>
        <property name="Bbox">None</property>

        <component name="Reference">
            <property name="safe"> {reference_zip} </property>
        </component>

        <component name="Secondary">
            <property name="safe"> {secondary_zip} </property>
        </component>

    </component>
</topsApp>
"""
    with open(output_path, 'w') as f:
        f.write(content)

def plot_pairs(all_df, valid_df, out_dir, show=False):
    """Plot all and valid interferometric pairs based on baseline and acquisition year.

    Args:
        all_df (pd.DataFrame): DataFrame with all selected interferometric pairs.
        valid_df (pd.DataFrame): DataFrame with only valid pairs (ZIPs found).
        out_dir (str): Directory to save plots and CSVs.
        show (bool): Whether to show the plot interactively.
    """

    def extract_baseline_and_year(df):
        years = []
        bperp = []
        for _, row in df.iterrows():
            try:
                date_str = row['master'].split('_')[5][:8]
                year_decimal = datetime.strptime(date_str, "%Y%m%d").year + \
                               (datetime.strptime(date_str, "%Y%m%d").timetuple().tm_yday / 365)
                years.append(year_decimal)

                orb_m = int(row['master'].split('_')[-2], 16)
                orb_s = int(row['slave'].split('_')[-2], 16)
                bperp.append(abs(orb_s - orb_m))
            except Exception as e:
                print(f"[!] Failed on {row['master']} - {row['slave']}: {e}")
                years.append(None)
                bperp.append(None)
        return years, bperp

    # ---- All Pairs ----
    yr_all, bp_all = extract_baseline_and_year(all_df)
    df_all = pd.DataFrame({'year': yr_all, 'bperp': bp_all})
    df_all.dropna().to_csv(os.path.join(out_dir, 'all_pairs_for_plot.csv'), index=False)
    print(f"[✓] Saved CSV: {os.path.join(out_dir, 'all_pairs_for_plot.csv')}")

    plt.figure(figsize=(10, 6))
    plt.scatter(df_all['year'], df_all['bperp'], c='lightgray', label='All pairs')
    plt.xlabel('Acquisition Year (decimal)')
    plt.ylabel('Perpendicular Baseline (m)')
    plt.title('All Interferometric Pairs')
    plt.grid(True)
    plt.savefig(os.path.join(out_dir, 'all_pairs_plot.png'))
    print(f"[✓] Saved plot: {os.path.join(out_dir, 'all_pairs_plot.png')}")
    if show:
        plt.show()
    plt.close()

    # ---- Valid Pairs ----
    yr_val, bp_val = extract_baseline_and_year(valid_df)
    df_val = pd.DataFrame({'year': yr_val, 'bperp': bp_val})
    df_val.dropna().to_csv(os.path.join(out_dir, 'valid_pairs_for_plot.csv'), index=False)
    print(f"[✓] Saved CSV: {os.path.join(out_dir, 'valid_pairs_for_plot.csv')}")

    plt.figure(figsize=(10, 6))
    plt.scatter(df_val['year'], df_val['bperp'], c='black', label='Valid pairs')
    plt.xlabel('Acquisition Year (decimal)')
    plt.ylabel('Perpendicular Baseline (m)')
    plt.title('Valid Interferometric Pairs (ZIPs found)')
    plt.grid(True)
    plt.savefig(os.path.join(out_dir, 'valid_pairs_plot.png'))
    print(f"[✓] Saved plot: {os.path.join(out_dir, 'valid_pairs_plot.png')}")
    if show:
        plt.show()
    plt.close()


def extract_bperp_from_name(name):
    try:
        return int(name.split('_')[-2], 16)
    except:
        return None


def main():
    parser = argparse.ArgumentParser(description='Generate ISCE2 topsApp.xml files from pair list.')
    parser.add_argument('--pairs', required=True, help='CSV file containing interferometric pairs (with columns: master, slave, path)')
    parser.add_argument('--data_path', required=True, help='Path to directory containing zipped .SAFE files')
    parser.add_argument('--output_dir', default='./isce2_xmls', help='Directory to store output XMLs')
    parser.add_argument('--dry_run', action='store_true', help='Only print matched pairs without writing XMLs')
    parser.add_argument('--plot', action='store_true', help='Show plots interactively in addition to saving them')

    args = parser.parse_args()
    df = pd.read_csv(args.pairs)
    os.makedirs(args.output_dir, exist_ok=True)

    valid_pairs = []
    missing_pairs = []

    counter = 0
    for _, row in df.iterrows():
        if counter >= 100000: 
            break
        counter += 1
        master, slave, path_str = row['master'], row['slave'], str(row['path'])

        path_folder = Path(args.data_path) / f"path_{path_str}"
        ref_zip = list(path_folder.glob(f'*{master}*.zip'))
        sec_zip = list(path_folder.glob(f'*{slave}*.zip'))

        if ref_zip and sec_zip:
            xml_name = f"{master}_{slave}_topsApp.xml"
            subdir = Path(args.output_dir) / f"path_{path_str}"
            os.makedirs(subdir, exist_ok=True)
            xml_path = subdir / xml_name

            if args.dry_run:
                print(f"\u2611 DRY_RUN: Would create {xml_path}")
            else:
                generate_topsApp_xml(str(ref_zip[0]), str(sec_zip[0]), xml_path)
                print(f"\u2705 XML ready: {xml_path}")
            valid_pairs.append([master, slave, path_str])
        else:
            print(f"\u26A0 Missing: {master} or {slave} in {path_folder}")
            missing_pairs.append([master, slave, path_str])

    # Save metadata
    pd.DataFrame(valid_pairs, columns=['master', 'slave', 'path']).to_csv(
        os.path.join(args.output_dir, 'valid_pairs.csv'), index=False
    )
    pd.DataFrame(missing_pairs, columns=['master', 'slave', 'path']).to_csv(
        os.path.join(args.output_dir, 'missing_pairs.csv'), index=False
    )

    # Log CLI arguments
    script_name = Path(__file__).name
    args_dict = {
        'pairs': (args.pairs, 'CSV with interferometric pair info'),
        'data_path': (args.data_path, 'Root directory containing .zip SAFE files'),
        'output_dir': (args.output_dir, 'Directory for topsApp XML outputs'),
        'dry_run': (args.dry_run, 'Simulate output without creating XML files'),
        'plot': (args.plot, 'Show plots interactively')
    }
    log_script_arguments(script_name, {k: v[0] for k, v in args_dict.items()},  # argument-value
                     {k: v[1] for k, v in args_dict.items()})              # argument-description
    df['Bperp'] = df.apply(lambda row: abs(
            extract_bperp_from_name(row['slave']) - extract_bperp_from_name(row['master'])), axis=1)

    # Plot results
    valid_df_plot = pd.DataFrame(valid_pairs, columns=['master', 'slave', 'path'])
    plot_pairs(df, valid_df_plot, args.output_dir, show=args.plot)

if __name__ == "__main__":
    main()
