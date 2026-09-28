import ftplib
import os
import zipfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import random

# Thread-local storage for FTP connections
thread_local = threading.local()

def get_ftp_connection(ftp_host, force_new=False):
    """Get or create an FTP connection for the current thread"""
    if force_new or not hasattr(thread_local, 'ftp'):
        # Close existing connection if any
        if hasattr(thread_local, 'ftp'):
            try:
                thread_local.ftp.quit()
            except:
                pass
        
        # Create new connection with timeout
        thread_local.ftp = ftplib.FTP()
        thread_local.ftp.connect(ftp_host, timeout=30)
        thread_local.ftp.login()
        thread_local.ftp.set_pasv(True)  # Use passive mode
        
    # Test if connection is still alive
    try:
        thread_local.ftp.voidcmd("NOOP")
    except:
        # Connection is dead, create a new one
        return get_ftp_connection(ftp_host, force_new=True)
    
    return thread_local.ftp

def explore_ftp_directory(ftp, path="/"):
    """
    Explore FTP directory structure to understand the layout
    """
    try:
        print(f"\nExploring directory: {path}")
        ftp.cwd(path)
        files_and_dirs = []
        ftp.retrlines('LIST', files_and_dirs.append)
        
        for item in files_and_dirs[:10]:  # Show first 10 items
            print(f"  {item}")
        if len(files_and_dirs) > 10:
            print(f"  ... and {len(files_and_dirs) - 10} more items")
        return files_and_dirs
    except Exception as e:
        print(f"Error exploring {path}: {e}")
        return []

def find_temperature_data_structure(ftp):
    """
    Explore the FTP to find where temperature data is located
    """
    print("Exploring PRISM FTP structure to find temperature data...")
    
    # Go to root
    ftp.cwd("/")
    root_contents = []
    ftp.retrlines('LIST', root_contents.append)
    
    print("\nRoot directory contents:")
    for item in root_contents:
        print(f"  {item}")
    
    # Check if old daily structure exists
    try:
        print("\nChecking old 'daily' structure...")
        ftp.cwd("/daily")
        daily_contents = []
        ftp.retrlines('LIST', daily_contents.append)
        print("Daily directory contents:")
        for item in daily_contents[:5]:
            print(f"  {item}")
        
        # Check if tmax exists in daily
        try:
            ftp.cwd("/daily/tmax")
            tmax_contents = []
            ftp.retrlines('LIST', tmax_contents.append)
            print(f"\nFound tmax directory with {len(tmax_contents)} items")
            
            # Check a few specific years
            for year in [2024, 2023, 2022, 2020]:
                try:
                    ftp.cwd(f"/daily/tmax")
                    year_contents = []
                    ftp.retrlines('LIST', year_contents.append)
                    year_files = [item for item in year_contents if str(year) in item]
                    if year_files:
                        print(f"Found {len(year_files)} files for year {year} in /daily/tmax/")
                        print(f"  Sample: {year_files[0] if year_files else 'None'}")
                except:
                    continue
                    
        except Exception as e:
            print(f"No tmax in daily: {e}")
            
    except Exception as e:
        print(f"No daily directory: {e}")
    
    # Check new time_series structure and available years
    try:
        print("\nChecking new 'time_series' structure...")
        ftp.cwd("/time_series")
        ts_contents = []
        ftp.retrlines('LIST', ts_contents.append)
        print("Time series directory contents:")
        for item in ts_contents:
            print(f"  {item}")
        
        # Check available years in the 800m tmax directory
        try:
            print("\nChecking available years in /time_series/us/an/800m/tmax/daily/:")
            ftp.cwd("/time_series/us/an/800m/tmax/daily/")
            year_dirs = []
            ftp.retrlines('LIST', year_dirs.append)
            available_years = []
            for item in year_dirs:
                # Extract year from directory listing
                parts = item.split()
                if len(parts) > 0:
                    dirname = parts[-1]
                    if dirname.isdigit() and len(dirname) == 4:
                        available_years.append(dirname)
            
            if available_years:
                print(f"Available years in 800m time_series: {', '.join(sorted(available_years))}")
            else:
                print("Could not determine available years")
                
        except Exception as e:
            print(f"Error checking available years: {e}")
            
    except Exception as e:
        print(f"No time_series directory: {e}")

def download_single_file_new(args):
    """Download a single file using new structure - for parallel execution with retry logic"""
    ftp_host, temp_var, date, temp_download_path, base_download_path = args
    
    year = date.year
    date_str = date.strftime("%Y%m%d")
    
    # New structure path: /time_series/us/an/800m/{var}/daily/{year}/
    ftp_path = f"/time_series/us/an/800m/{temp_var}/daily/{year}/"
    
    # New filename format: prism_{var}_us_30s_{date}.zip (30s = 800m)
    filename = f"prism_{temp_var}_us_30s_{date_str}.zip"
    local_zip_path = os.path.join(temp_download_path, filename)
    
    # Retry logic
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            # Add random delay to avoid overwhelming the server
            if attempt > 0:
                delay = retry_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(delay)
            
            ftp = get_ftp_connection(ftp_host, force_new=(attempt > 0))
            
            # Try to change to the directory
            try:
                ftp.cwd(ftp_path)
            except ftplib.error_perm as e:
                # Directory might not exist for this year/variable
                if attempt == 0:  # Only print on first attempt
                    print(f"[{threading.current_thread().name}] Directory not found: {ftp_path} - {str(e)}")
                return False, f"{filename} (dir not found)"
            
            # Try to download the file
            try:
                # Create temp file with different name to avoid conflicts
                temp_filename = f"{filename}.{threading.current_thread().ident}.tmp"
                temp_path = os.path.join(temp_download_path, temp_filename)
                
                with open(temp_path, 'wb') as local_file:
                    ftp.retrbinary(f"RETR {filename}", local_file.write, blocksize=8192)
                
                # Rename temp file to final name
                os.rename(temp_path, local_zip_path)
                
                if attempt > 0:
                    print(f"[{threading.current_thread().name}] Successfully downloaded {filename} on attempt {attempt + 1}")
                
            except ftplib.error_perm as e:
                if "550" in str(e):
                    # File not found - common for dates without data
                    return False, f"{filename} (file not found)"
                else:
                    if attempt == max_retries - 1:
                        print(f"[{threading.current_thread().name}] FTP error for {filename} after {max_retries} attempts: {str(e)}")
                    raise  # Will trigger retry
            except (EOFError, ftplib.error_temp, ConnectionResetError) as e:
                if attempt == max_retries - 1:
                    print(f"[{threading.current_thread().name}] Connection error for {filename} after {max_retries} attempts: {type(e).__name__}")
                    return False, f"{filename} (connection error after {max_retries} attempts)"
                continue  # Retry
            
            # Extract and rename the TIF file
            if extract_and_rename_tif(local_zip_path, temp_var, date_str, base_download_path):
                # Clean up the zip file
                os.remove(local_zip_path)
                return True, filename
            else:
                return False, f"{filename} (extract failed)"
                
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"[{threading.current_thread().name}] Unexpected error with {filename} after {max_retries} attempts: {type(e).__name__}: {str(e)}")
                # Clean up partial download if exists
                for f in [local_zip_path, os.path.join(temp_download_path, f"{filename}.{threading.current_thread().ident}.tmp")]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except:
                            pass
                return False, f"{filename} (error: {type(e).__name__})"
            continue  # Retry
    
    return False, f"{filename} (failed after {max_retries} attempts)"

def download_single_file_old(args):
    """Download a single file using old structure - for parallel execution"""
    ftp_host, temp_var, date, temp_download_path, base_download_path = args
    
    date_str = date.strftime("%Y%m%d")
    
    # Try different filename patterns commonly used
    possible_filenames = [
        f"PRISM_{temp_var}_stable_4kmD2_{date_str}_bil.zip",
        f"PRISM_{temp_var}_stable_4kmD1_{date_str}_bil.zip",
        f"PRISM_{temp_var}_provisional_4kmD2_{date_str}_bil.zip",
        f"PRISM_{temp_var}_provisional_4kmD1_{date_str}_bil.zip",
        f"PRISM_{temp_var}_early_4kmD2_{date_str}_bil.zip",
        f"PRISM_{temp_var}_early_4kmD1_{date_str}_bil.zip",
    ]
    
    for filename in possible_filenames:
        try:
            ftp = get_ftp_connection(ftp_host)
            ftp.cwd(f"/daily/{temp_var}")
            
            local_zip_path = os.path.join(temp_download_path, filename)
            
            print(f"[Thread {threading.current_thread().name}] Trying {filename}...")
            with open(local_zip_path, 'wb') as local_file:
                ftp.retrbinary(f"RETR {filename}", local_file.write)
            
            # Extract and rename the TIF file
            if extract_and_rename_tif_old(local_zip_path, temp_var, date_str, base_download_path):
                # Clean up the zip file
                os.remove(local_zip_path)
                return True, f"{temp_var}_{date_str}"
            else:
                return False, f"{temp_var}_{date_str}"
                
        except ftplib.error_perm as e:
            if "550" in str(e):  # File not found
                continue
            else:
                print(f"[Thread {threading.current_thread().name}] Error downloading {filename}: {e}")
                continue
        except Exception as e:
            print(f"[Thread {threading.current_thread().name}] Unexpected error with {filename}: {e}")
            continue
    
    return False, f"{temp_var}_{date_str}"

def download_prism_temperature_data(years, max_workers=4):
    """
    Download PRISM temperature data for May 1 - September 30 for specified years
    Variables: tmax, tmin, tmean
    Resolution: 800m
    Region: CONUS (us)
    """
    
    # Configuration
    ftp_host = "prism.oregonstate.edu"
    base_download_path = r"~\hennepin\data\raw\prism"
    temp_download_path = os.path.join(base_download_path, "temp_downloads")
    
    # Create directories if they don't exist
    Path(base_download_path).mkdir(parents=True, exist_ok=True)
    Path(temp_download_path).mkdir(parents=True, exist_ok=True)
    
    # Temperature variables to download
    temp_vars = ['tmax', 'tmin', 'tmean']
    
    # Generate list of dates for all years
    dates = []
    for year in years:
        # Date range: May 1 to September 30 for each year
        start_date = datetime(year, 5, 1)
        end_date = datetime(year, 9, 30)
        
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)
    
    print(f"Will download {len(dates)} days × {len(temp_vars)} variables = {len(dates) * len(temp_vars)} files")
    print(f"Years: {', '.join(map(str, years))}")
    print(f"Date range: May 1 - September 30 for each year")
    print(f"Using {max_workers} parallel workers")
    
    try:
        # Connect to FTP server for initial exploration
        print("\nConnecting to PRISM FTP server...")
        ftp = ftplib.FTP(ftp_host)
        ftp.login()  # Anonymous login
        print("Connected successfully!")
        
        # First, explore the directory structure
        find_temperature_data_structure(ftp)
        
        # Ask user for confirmation to proceed
        print(f"\nBased on the directory exploration above, choose download method:")
        print("1. Try new time_series structure (recommended for 800m data)")
        print("2. Try old daily structure (4km BIL format)")
        print("3. Exit and manual investigation")
        
        choice = input("Enter choice (1, 2, or 3): ").strip()
        
        if choice == "3":
            print("Exiting for manual investigation.")
            ftp.quit()
            return False
        
        # Close the exploration connection
        ftp.quit()
        
        # Prepare download tasks
        download_tasks = []
        for temp_var in temp_vars:
            for date in dates:
                download_tasks.append((ftp_host, temp_var, date, temp_download_path, base_download_path))
        
        # Execute downloads in parallel
        downloaded_files = 0
        failed_downloads = []
        
        print(f"\nStarting parallel downloads with {max_workers} workers...")
        print(f"Total files to download: {len(download_tasks)}")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            if choice == "2":
                # Use old structure
                future_to_task = {executor.submit(download_single_file_old, task): task for task in download_tasks}
            else:
                # Use new structure
                future_to_task = {executor.submit(download_single_file_new, task): task for task in download_tasks}
            
            # Process completed downloads
            completed = 0
            for future in as_completed(future_to_task):
                completed += 1
                success, info = future.result()
                if success:
                    downloaded_files += 1
                else:
                    failed_downloads.append(info)
                
                # Progress update
                if completed % 10 == 0 or completed == len(download_tasks):
                    print(f"Progress: {completed}/{len(download_tasks)} attempted, {downloaded_files} successful")
        
        print(f"\nDownload completed!")
        print(f"Successfully downloaded: {downloaded_files} files")
        print(f"Failed downloads: {len(failed_downloads)} files")
        
        if failed_downloads:
            # Analyze failure reasons
            failure_reasons = {}
            for failed in failed_downloads:
                if "dir not found" in failed:
                    reason = "Directory not found (year might not be available)"
                elif "file not found" in failed:
                    reason = "File not found (date might not have data)"
                elif "connection error" in failed or "EOFError" in failed:
                    reason = "Connection error (FTP timeout/disconnect)"
                elif "ftp error" in failed:
                    reason = "FTP error"
                elif "extract failed" in failed:
                    reason = "Extract/conversion failed"
                else:
                    reason = "Other error"
                
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
            
            print("\nFailure summary:")
            for reason, count in failure_reasons.items():
                print(f"  - {reason}: {count} files")
            
            print(f"\nShowing first 10 failed files:")
            for failed in failed_downloads[:10]:
                print(f"  - {failed}")
            if len(failed_downloads) > 10:
                print(f"  ... and {len(failed_downloads) - 10} more")
                
            # Check if all files failed due to directory issues
            if "Directory not found (year might not be available)" in failure_reasons and \
               failure_reasons["Directory not found (year might not be available)"] > len(download_tasks) * 0.9:
                print("\n⚠️  Most failures are due to missing directories.")
                print("The selected years might not be available in the 800m time_series structure.")
                print("Try option 2 (old daily structure) for older years.")
            
            # Check if many failures are due to connection errors
            connection_errors = sum(count for reason, count in failure_reasons.items() 
                                  if "connection error" in reason or "EOFError" in reason)
            if connection_errors > len(download_tasks) * 0.3:
                print("\n⚠️  Many failures are due to connection errors.")
                print("This usually happens when:")
                print("  1. Too many parallel workers are overwhelming the server")
                print("  2. The FTP server is limiting concurrent connections")
                print("  3. Network connectivity issues")
                print("\nSuggestions:")
                print(f"  - Reduce MAX_WORKERS (currently {max_workers}) to 2-4")
                print("  - Try running the script again - it has retry logic")
                print("  - Check your internet connection stability")
        
        # Clean up temp directory
        if os.path.exists(temp_download_path):
            shutil.rmtree(temp_download_path)
            print("\nTemporary files cleaned up.")
        
        return downloaded_files > 0
            
    except Exception as e:
        print(f"Error: {e}")
        return False

def extract_and_rename_tif(zip_path, var, date_str, output_dir):
    """
    Extract TIF file from zip and rename according to specified format
    Format: <var>_prism_<yyyymmdd>_800m.tif
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # List all files in the zip
            file_list = zip_ref.namelist()
            
            # Find the .tif file (should be only one)
            tif_files = [f for f in file_list if f.endswith('.tif')]
            
            if len(tif_files) != 1:
                print(f"Warning: Expected 1 TIF file, found {len(tif_files)} in {zip_path}")
                return False
            
            tif_file = tif_files[0]
            
            # Extract to temporary location
            zip_ref.extract(tif_file, output_dir)
            
            # Construct new filename: <var>_prism_<yyyymmdd>_800m.tif
            new_filename = f"{var}_prism_{date_str}_800m.tif"
            
            # Move and rename the file
            old_path = os.path.join(output_dir, tif_file)
            new_path = os.path.join(output_dir, new_filename)
            
            shutil.move(old_path, new_path)
            
            # Clean up any extracted directories
            extracted_dir = os.path.dirname(old_path)
            if extracted_dir != output_dir and os.path.exists(extracted_dir):
                shutil.rmtree(extracted_dir)
            
            print(f"  -> Saved as {new_filename}")
            return True
            
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        return False

def extract_and_rename_tif_old(zip_path, var, date_str, output_dir):
    """
    Extract BIL/TIF files from old structure zip and convert/rename
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # List all files in the zip
            file_list = zip_ref.namelist()
            
            # Find the main data file (.bil or .tif)
            data_files = [f for f in file_list if f.endswith(('.bil', '.tif'))]
            
            if len(data_files) == 0:
                print(f"Warning: No data files found in {zip_path}")
                return False
            
            # Use the first data file found
            data_file = data_files[0]
            
            # Extract all files to temporary location (BIL files need their supporting files)
            extract_dir = os.path.join(output_dir, f"temp_extract_{os.getpid()}_{threading.current_thread().ident}")
            zip_ref.extractall(extract_dir)
            
            # Construct new filename: <var>_prism_<yyyymmdd>_800m.tif
            new_filename = f"{var}_prism_{date_str}_800m.tif"
            
            # If it's a BIL file, we need to convert to TIF using GDAL or rasterio
            old_path = os.path.join(extract_dir, data_file)
            new_path = os.path.join(output_dir, new_filename)
            
            if data_file.endswith('.bil'):
                # Try to convert BIL to TIF using rasterio
                try:
                    import rasterio
                    with rasterio.open(old_path) as src:
                        profile = src.profile
                        profile.update(driver='GTiff')
                        
                        with rasterio.open(new_path, 'w', **profile) as dst:
                            dst.write(src.read())
                    print(f"  -> Converted BIL to TIF and saved as {new_filename}")
                except ImportError:
                    print(f"  -> Warning: rasterio not available, copying BIL as-is")
                    shutil.copy2(old_path, new_path.replace('.tif', '.bil'))
                except Exception as e:
                    print(f"  -> Error converting BIL: {e}")
                    return False
            else:
                # Just move the TIF file
                shutil.move(old_path, new_path)
                print(f"  -> Saved as {new_filename}")
            
            # Clean up extracted directory
            shutil.rmtree(extract_dir)
            
            return True
            
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        return False

def verify_downloads(years):
    """
    Verify that all expected files were downloaded
    """
    base_path = r"~\hennepin\data\raw\prism"
    temp_vars = ['tmax', 'tmin', 'tmean']
    
    # Generate expected dates for all years
    expected_dates = []
    for year in years:
        start_date = datetime(year, 5, 1)
        end_date = datetime(year, 9, 30)
        current_date = start_date
        while current_date <= end_date:
            expected_dates.append(current_date.strftime("%Y%m%d"))
            current_date += timedelta(days=1)
    
    print(f"\nVerifying downloads in {base_path}...")
    
    missing_files = []
    found_files = 0
    
    for var in temp_vars:
        for date_str in expected_dates:
            expected_filename = f"{var}_prism_{date_str}_800m.tif"
            file_path = os.path.join(base_path, expected_filename)
            
            if os.path.exists(file_path):
                found_files += 1
            else:
                missing_files.append(expected_filename)
    
    total_expected = len(temp_vars) * len(expected_dates)
    print(f"Found {found_files}/{total_expected} expected files")
    
    if missing_files:
        print(f"\nMissing {len(missing_files)} files:")
        for missing in missing_files[:10]:  # Show first 10 missing files
            print(f"  - {missing}")
        if len(missing_files) > 10:
            print(f"  ... and {len(missing_files) - 10} more")
    else:
        print("All files downloaded successfully!")

if __name__ == "__main__":
    # ===== CONFIGURATION =====
    # Specify which years to download
    YEARS_TO_DOWNLOAD = [2021]
    
    # Number of parallel download workers (adjust based on your system and connection)
    # WARNING: Too many workers can overwhelm the FTP server and cause connection errors!
    # Recommended: 2-6 workers for stable downloads
    MAX_WORKERS = 8  # Number of simultaneous downloads
    # ========================
    
    print("PRISM Temperature Data Downloader")
    print("=================================")
    print(f"Downloading daily temperature data for May 1 - September 30")
    print(f"Years: {', '.join(map(str, YEARS_TO_DOWNLOAD))}")
    print(f"Variables: tmax, tmin, tmean")
    print(f"Resolution: 800m (or 4km if 800m not available)")
    print(f"Region: CONUS")
    print(f"Parallel workers: {MAX_WORKERS}")
    
    if MAX_WORKERS > 8:
        print("\n⚠️  WARNING: Using more than 8 workers may cause connection errors!")
        print("The PRISM FTP server may limit concurrent connections.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting. Please reduce MAX_WORKERS and try again.")
            exit(0)
    
    print()
    
    success = download_prism_temperature_data(YEARS_TO_DOWNLOAD, MAX_WORKERS)
    
    if success:
        verify_downloads(YEARS_TO_DOWNLOAD)
    else:
        print("Download failed. Please check your internet connection and try again.")