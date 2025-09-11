import subprocess
import argparse
import re

def list_unique_variables(nc_file):
    """
    Extracts unique variable base names from a NetCDF file.

    Parameters:
        nc_file (str): Path to the NetCDF file.

    Returns:
        list: A list of unique variable base names.
    """
    try:
        command = f"ncdump -h {nc_file} | grep -o '^[[:space:]]*float [^ ]*' | awk '{{print $2}}'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        variables = result.stdout.strip().split("\n")

        # Extract base variable names (removing year suffixes)
        unique_vars = sorted(set(re.sub(r'_\d{4}$', '', var) for var in variables if var))

        return unique_vars
    except subprocess.CalledProcessError as e:
        print("\u274C Error listing variables:", e)  
        return []

def extract_selected_variables(nc_file, selected_vars, start_year, end_year):
    """
    Extracts multiple selected variables for a specific time range from a NetCDF file.

    Parameters:
        nc_file (str): Path to the NetCDF file.
        selected_vars (list): List of selected variable base names.
        start_year (int): Start year for extraction.
        end_year (int): End year for extraction.

    Returns:
        str: Path to the extracted NetCDF file.
    """
    selected_vars_str = "_".join(selected_vars)
    output_file = nc_file.replace(".nc", f"_{selected_vars_str}_{start_year}_{end_year}.nc")

    # Generate list of variable names with years
    year_variables = []
    for year in range(start_year, end_year + 1):
        for var in selected_vars:
            year_variables.append(f"{var}_{year}")

    variables_str = ",".join(year_variables)
    extract_command = f"ncks -v {variables_str} -O {nc_file} {output_file}"

    print(f"\U0001F504 Running extraction command: {extract_command}")  
    try:
        subprocess.run(extract_command, shell=True, check=True)
        print(f"\u2705 Extracted {selected_vars} for {start_year}-{end_year} into {output_file}")  # ✅
        return output_file
    except subprocess.CalledProcessError as e:
        print("\u274C Error extracting variables:", e)  
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract selected variables over a time range from a NetCDF file.")
    parser.add_argument("--input", required=True, help="Path to the NetCDF file")

    args = parser.parse_args()
    nc_file = args.input

    # List unique variable types
    variables = list_unique_variables(nc_file)
    if not variables:
        print("\u274C No variables found.")  
        exit()

    # Display available base variable names
    print("Available variable types in NetCDF file:")  
    for idx, var in enumerate(variables):
        print(f"{idx+1}. {var}")

    # Ask user to select variables
    choices = input("\n\U0001F50D Enter the numbers of the variables to extract (comma-separated, e.g., 1,3,5): ")  # 🔍
    try:
        selected_indices = [int(choice.strip()) - 1 for choice in choices.split(",")]
        selected_vars = [variables[i] for i in selected_indices if 0 <= i < len(variables)]
        
        if not selected_vars:
            print("\u274C No valid variables selected.")  
            exit()

        # Prompt for start and end years
        start_year = int(input("\U0001F4C5 Enter the start year (e.g., 2010): "))  
        end_year = int(input("\U0001F4C6 Enter the end year (e.g., 2024): "))  

        if start_year > end_year:
            print("\u274C Start year cannot be greater than end year.")  
            exit()

        extract_selected_variables(nc_file, selected_vars, start_year, end_year)

    except ValueError:
        print("\u274C Please enter valid numbers.")  
