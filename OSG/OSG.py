import pandas as pd
import os
import pyarrow.parquet as pq
import pyarrow as pa
import warnings
warnings.filterwarnings('ignore')
import ipywidgets as widgets
from IPython.display import display, clear_output

# ========================== STEP 1: Get Initial Inputs ==========================
def get_initial_input_from_user(path: str, df_metadata: pd.DataFrame):
    """Gets the path to the raw data from users and generates a list of the files.
    
    Args:
    - path: The path to the raw data.
    - df_metadata: The metadata describing household characteristics.

    Returns:
    - filtered_files: List of all raw data files with thermostats including built-in motion sensors.
    """
    if not os.path.exists(path):
        print(f"'{path}' is not a valid directory path.")
        return None, None

    # Filter only the models with built-in motion sensors
    model = ['ecobee4', 'ESTWVC', 'ecobee3', 'SmartSi']
    df_ilg = df_metadata[df_metadata['model'].isin(model)]
    files = list(df_ilg['identifier'])
    
    if not files:
        print("No eligible houses found.")
        return None, None

    # List all files in the directory
    files_path = [os.path.join(path, file) for file in os.listdir(path)]
    print(f"Total number of files: {len(files_path)}")
    print("The filtering process is starting now.")
    
    return files_path, files

# ========================== STEP 2: Filter Sensor Data ==========================
def filter_sensor_data(files_path: list, files, output_folder="Filtered_Houses"):
    """Filter occupancy data and save each house separately in a new folder.
    
    Args:
    - files_path: List of all raw data files with full paths.
    - files: List of house identifiers to filter.
    - output_folder: Folder to save filtered data.

    Returns:
    - output_folder: Path to the new folder containing filtered data.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    print(f"Processing raw data and saving to {output_folder}...")

    progress_bar = widgets.IntProgress(value=0, min=0, max=len(files_path), description='Processing:', orientation='horizontal')
    display(progress_bar)

    for file in files_path:
        file_name, ext = os.path.splitext(file)
        df = pd.read_parquet(file) if ext.lower() == '.parquet' else pd.read_csv(file, dtype={'Identifier': 'category'})

        for house in df.Identifier.unique():
            if house in files:
                df_1 = df[df.Identifier == house].copy()
                occ_columns = [col for col in df_1.columns if 'Occ' in col]
                if occ_columns:
                    df_1 = df_1[['date_time', 'Identifier'] + occ_columns]
                    df_1[occ_columns] = df_1[occ_columns].astype(float)
                    df_1['date_time'] = pd.to_datetime(df_1['date_time'])
                    df_1['hour'] = df_1['date_time'].dt.hour
                    df_1['date'] = df_1['date_time'].dt.date 

                    house_file_path = os.path.join(output_folder, f"{house}.parquet")
                    df_1.to_parquet(house_file_path, index=False, engine="pyarrow", compression="snappy")
        
        progress_bar.value += 1

    print(f"Filtering completed. All houses saved to {output_folder}.")
    return output_folder  

# ====================== STEP 3: Compute Hourly Averages =========================
def occupancy_hourly_average(folder_path):
    """Compute hourly occupancy averages for each house separately.
    
    Args:
    - folder_path: Path to the folder containing filtered Parquet files.

    Returns:
    - folder_path: Path to the folder containing aggregated Parquet files.
    """
    
    print(f"Processing hourly averages and saving back to {folder_path}...")
    
    for file in os.listdir(folder_path):
        if file.endswith(".parquet"):
            file_path = os.path.join(folder_path, file)
            df_total = pd.read_parquet(file_path)

            df_total['number_sensors'] = df_total.filter(like='Occ').notna().sum(axis=1).astype('int8')
            df_total['average_occ'] = df_total.filter(like='Occ').mean(axis=1).astype('float32')

            df_houses = df_total.groupby(['Identifier', 'date', 'hour']).agg({
                'average_occ': 'mean',
                'number_sensors': 'max'
            }).reset_index()

            df_houses['Identifier'] = df_houses['Identifier'].astype('category')

            df_houses.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")

    print("Hourly aggregation completed.")
    return folder_path  

# ======================= STEP 4: Compute Occupancy Status ========================
def get_quantile_inputs_from_users():
    """Create UI widgets for user input on working, non-working, and weekend hours."""

    message_label = widgets.Label('Please choose different values for the 3-hour types')

    dropdown_working = widgets.Dropdown(options=['working hours', 'nonworking hours', 'weekend hours'], description='Metric (1)')
    slider_working = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')

    dropdown_nonworking = widgets.Dropdown(options=['nonworking hours', 'working hours', 'weekend hours'], description='Metric (2)')
    slider_nonworking = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')

    dropdown_weekend = widgets.Dropdown(options=['weekend hours', 'working hours', 'nonworking hours'], description='Metric (3)')
    slider_weekend = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')

    dropdown_night_start = widgets.Dropdown(options=list(range(24)), description='Night Start:')
    dropdown_night_end = widgets.Dropdown(options=list(range(24)), description='Night End:')

    def update_message(*args):
        selected_values = [dropdown_working.value, dropdown_nonworking.value, dropdown_weekend.value]
        if len(set(selected_values)) == 3:
            message_label.value = 'Selection complete. Please also define night hours.'
        else:
            message_label.value = 'Please choose different values for the 3-hour types.'

    dropdown_working.observe(update_message, names='value')
    dropdown_nonworking.observe(update_message, names='value')
    dropdown_weekend.observe(update_message, names='value')

    # Display UI elements
    display(message_label, dropdown_working, slider_working, dropdown_nonworking, slider_nonworking,
            dropdown_weekend, slider_weekend, dropdown_night_start, dropdown_night_end)

    return (dropdown_working, slider_working, dropdown_nonworking, slider_nonworking,
            dropdown_weekend, slider_weekend, dropdown_night_start, dropdown_night_end)
    
def occupancy_status_profile(folder_path, wd):
    """Convert the average occupancy to binary (0 or 1) for each house separately.
    
    Args:
    - folder_path: Path to the folder containing aggregated Parquet files.
    - wd: User-defined quantile values from sliders.

    Returns:
    - folder_path: Path to the folder containing the final processed files.
    """
    print("Applying occupancy status transformation...")

    for file in os.listdir(folder_path):
        if file.endswith(".parquet"):
            file_path = os.path.join(folder_path, file)
            df_houses = pd.read_parquet(file_path)

            df_houses['date'] = pd.to_datetime(df_houses['date'])
            df_houses['weekday'] = df_houses['date'].dt.weekday
            df_houses['day_type'] = df_houses['weekday'].apply(lambda x: 'weekend' if x >= 5 else 'weekday')

            metric_working = wd[1].value / 100
            metric_nonworking = wd[3].value / 100
            metric_weekend = wd[5].value / 100

            df_houses['Occupancy'] = (df_houses['average_occ'] >= df_houses.groupby(['Identifier', 'hour', 'day_type'])['average_occ'].transform(lambda x: x.quantile(metric_working if 'working' in x.name else metric_nonworking if 'nonworking' in x.name else metric_weekend))).astype('int8')

            # ✅ Ensure `date_time` exists
            df_houses['date_time'] = df_houses['date'] + pd.to_timedelta(df_houses['hour'], unit='h')

            df_houses.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")

    print("Occupancy transformation completed.")
    return folder_path  
 

# =========================== STEP 5: Display Results ============================
def display_results(folder_path):
    """Display aggregated occupancy probability from processed Parquet files."""
    print("Generating results visualization...")

    percentages = []
    house_count = 0

    for file in os.listdir(folder_path):
        if file.endswith(".parquet"):
            file_path = os.path.join(folder_path, file)
            df_final = pd.read_parquet(file_path)

            house_count += 1
            house_percentages = df_final.groupby(df_final['date_time'].dt.hour)['Occupancy'].mean()
            percentages.append(house_percentages)

    aggregated_percentages = pd.concat(percentages, axis=1).mean(axis=1)

    plt.figure(figsize=(10, 6))
    plt.plot(aggregated_percentages.index, aggregated_percentages.values, marker='o', linestyle='-', linewidth=2)
    plt.xlabel('Hour of the Day')
    plt.ylabel('Aggregated Occupied Probability')
    plt.title('Aggregated Occupied Probability by Hour of the Day')
    plt.xticks(range(0, 24))
    plt.grid(True)
    plt.show()

    print(f"Number of houses analyzed: {house_count}")
    print(f"Average occupied hours: {round(aggregated_percentages.mean() * 100, 2)}%")

# =========================== FINAL EXECUTION FLOW ==============================
def update_results(wd, folder_path):
    """Recompute occupancy status and update results dynamically."""
    folder = occupancy_status_profile(folder_path, wd)
    display_results(folder)

def start(path: str, df_metadata: pd.DataFrame):
    """Pipeline execution to filter, process, and analyze occupancy data interactively.
    
    Args:
    - path: The path to the raw data.
    - df_metadata: The metadata describing the household characteristics.
    
    Returns:
    - Final folder path containing processed occupancy data.
    """
    
    files, filter_files = get_initial_input_from_user(path, df_metadata)
    if files is None:
        return

    folder = filter_sensor_data(files, filter_files)
    folder = occupancy_hourly_average(folder)

    # Collect user inputs
    wd = get_quantile_inputs_from_users()

    # **Dynamic Update: Automatically update results when user changes values**
    def on_change(change):
        update_results(wd, folder)

    wd[1].observe(on_change, names='value')  # Working Hours Slider
    wd[3].observe(on_change, names='value')  # Nonworking Hours Slider
    wd[5].observe(on_change, names='value')  # Weekend Hours Slider

    update_results(wd, folder)  # Initial results

    return folder

