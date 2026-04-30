#!/usr/bin/env python3
"""
Select interferometric pairs from SLC database, handling multiple frames per date.
Groups SLCs by acquisition date first, then pairs different dates.
"""

import psycopg2
import pandas as pd
import argparse

def select_pairs_by_date(db_name, table_name='slc_data', bmax=100, tmax=48, user='postgres', host='localhost'):
    """
    Select interferometric pairs, grouping by acquisition date to avoid same-day pairs.
    
    NOTE: Bperp filtering is disabled because orbit numbers are not perpendicular baselines.
    Real Bperp requires precise orbit files (.EOF) which will be downloaded separately.
    ISCE2's stackSentinel will calculate proper baselines during processing.
    """
    
    # Connect and query
    conn = psycopg2.connect(dbname=db_name, user=user, host=host)
    query = f"SELECT granule_name, acquisition_date, path_number, orbit FROM {table_name} ORDER BY acquisition_date, granule_name;"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Total SLCs in database: {len(df)}")
    print(f"Unique acquisition dates: {df['acquisition_date'].nunique()}")
    print(f"SLCs per date (mean): {len(df) / df['acquisition_date'].nunique():.1f}")
    print()
    
    # Group by acquisition date and select one representative SLC per date
    # Choose the first frame alphabetically (consistent selection)
    df_dates = df.groupby('acquisition_date').first().reset_index()
    
    print(f"After grouping by date: {len(df_dates)} unique dates")
    print()
    
    print("⚠️  NOTE: Bperp filtering disabled (orbit# ≠ perpendicular baseline)")
    print("   ISCE2 will calculate proper baselines from orbit files during processing")
    print()
    
    # Now select pairs (TEMPORAL BASELINE ONLY)
    pairs = []
    for path in df_dates['path_number'].unique():
        df_path = df_dates[df_dates['path_number'] == path].reset_index(drop=True)
        
        for i in range(len(df_path)):
            for j in range(i + 1, len(df_path)):
                date1 = df_path.loc[i, 'acquisition_date']
                date2 = df_path.loc[j, 'acquisition_date']
                
                # Calculate temporal baseline
                delta_t = abs((date2 - date1).days)
                
                if delta_t > 0 and delta_t <= tmax:
                    # Note: orbit number stored for reference, not actual Bperp
                    orbit_diff = abs(df_path.loc[j, 'orbit'] - df_path.loc[i, 'orbit'])
                    
                    pairs.append({
                        'master': df_path.loc[i, 'granule_name'],
                        'slave': df_path.loc[j, 'granule_name'],
                        'master_date': date1,
                        'slave_date': date2,
                        'path': path,
                        'orbit_diff': orbit_diff,  # NOT perpendicular baseline!
                        'delta_days': delta_t
                    })
    
    return pd.DataFrame(pairs)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Select interferometric pairs from SLC database (handles multiple frames per date)"
    )
    parser.add_argument('--db_name', required=True, help='PostgreSQL database name')
    parser.add_argument('--table_name', default='slc_data', help='Database table name')
    parser.add_argument('--bmax', type=float, default=100.0, help='Maximum perpendicular baseline (meters)')
    parser.add_argument('--tmax', type=int, default=48, help='Maximum temporal baseline (days)')
    parser.add_argument('--output', default='sel_pairs.csv', help='Output CSV filename')
    parser.add_argument('--user', default='postgres', help='PostgreSQL username')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    
    args = parser.parse_args()
    
    print("="*80)
    print("INTERFEROMETRIC PAIR SELECTION")
    print("="*80)
    print(f"Database: {args.db_name}")
    print(f"Max temporal baseline: {args.tmax} days")
    print(f"Max perpendicular baseline: {args.bmax} meters")
    print()
    
    # Select pairs
    df_pairs = select_pairs_by_date(
        args.db_name,
        args.table_name,
        args.bmax,
        args.tmax,
        args.user,
        args.host
    )
    
    if len(df_pairs) == 0:
        print("⚠️  No valid pairs found with these constraints!")
        exit(1)
    
    # Save to CSV
    df_pairs.to_csv(args.output, index=False)
    
    print("="*80)
    print("PAIR STATISTICS")
    print("="*80)
    print(f"Total pairs: {len(df_pairs)}")
    print(f"\nTemporal baseline:")
    print(f"  • Min:  {df_pairs['delta_days'].min()} days")
    print(f"  • Max:  {df_pairs['delta_days'].max()} days")
    print(f"  • Mean: {df_pairs['delta_days'].mean():.1f} days")
    print(f"\nOrbit number difference (NOT Bperp!):")
    print(f"  • Min:  {df_pairs['orbit_diff'].min()}")
    print(f"  • Max:  {df_pairs['orbit_diff'].max()}")
    print(f"  • Mean: {df_pairs['orbit_diff'].mean():.1f}")
    print()
    print(f"✅ Saved {len(df_pairs)} pairs to: {args.output}")
    print()
    print("Next steps:")
    print("1. Download orbit files:")
    print(f"   python download_orbits_for_slcs.py \\")
    print(f"     --slc-dir /mnt/data/sbas_vs_ps_test_bologna/data/safe \\")
    print(f"     --orbit-dir /mnt/data/sbas_vs_ps_test_bologna/data/orbit")
    print()
    print("2. ISCE2 will calculate proper Bperp during stackSentinel processing")
