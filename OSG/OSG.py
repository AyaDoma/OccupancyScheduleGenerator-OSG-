import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')
import ipywidgets as widgets
from IPython.display import display, clear_output

def get_initial_input_form_user(path: str, df_metadata: pd.DataFrame):
    """ Gets the path to the raw data from users and generate list of the files
    
    Args:
    - path: the path to the raw data
    - df_metadata: The metadata descripting the household characteristics.
    if not valid the code will break and report an error
    
    Returns:
    - filtered_files: list of all the raw data files with thermostat models includes built-in motion sensor.
    
    """
    def is_valid_path(path):
        return os.path.isfile(path) or os.path.isdir(path)
    
    if not is_valid_path(path):
        print(f"'{path}' is not a valid file or directory path.")
        return None, None
    else:
        model = ['ecobee4', 'ESTWVC', 'ecobee3', 'SmartSi']
        df_ilg = df_metadata[df_metadata['model'].isin(model)]
        files = list(df_ilg['identifier'])
        if not files:
            print("No illegible houses")
            return None, None
        files_path = [os.path.join(path, file) for file in os.listdir(path)]
        print(f"Total number of files= {len(files_path)}")
        print("The filtering process is starting now")
        return files_path, files
        
#------------------------------------------------------------------------------------
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
                occ_columns = [col for col in df_1.columns if 'Occ' in col] #motion sensor columns 
                if occ_columns:
                    df_1 = df_1[['date_time', 'Identifier'] + occ_columns]
                    df_1[occ_columns] = df_1[occ_columns].astype(float)# changing the type 
                    df_1['date_time'] = pd.to_datetime(df_1['date_time'])
                    df_1['hour'] = df_1['date_time'].dt.hour
                    df_1['date'] = df_1['date_time'].dt.date 

                    house_file_path = os.path.join(output_folder, f"{house}.parquet")
                    df_1.to_parquet(house_file_path, index=False, engine="pyarrow", compression="snappy")
        
        progress_bar.value += 1
        
    if not os.listdir(output_folder): 
        print("No Occupancy data in the files")
    else:
        print(f"Filtering completed. All houses saved to {output_folder}.")
    return output_folder  
    
#----------------------------------------------------------------------------------
def occupancy_hourly_average(output_folder):
    """ Starts the aggregation process with calculating the average reading for each day.
    
     Args:
    - output_folder: the path to the filtered houses with only occupancy data
    
    Returns:
    - Output_folder: path to dataframe for each house with the following columns (date, hour, average_occ, Identifier, number_sensors)
    """
    for file in os.listdir(output_folder):
        file_path = os.path.join(output_folder, file)
        df_total = pd.read_parquet(file_path)
        df_total['number_sensors'] = df_total.filter(like='Occ').notna().sum(axis=1).astype('int8')
        df_total['average_occ'] = df_total.filter(like='Occ').mean(axis=1).astype('float32')
        df_houses = df_total.groupby(['Identifier', 'date', 'hour']).agg({
            'average_occ': 'mean',
            'number_sensors': 'max'
        }).reset_index()
        df_houses['Identifier'] = df_houses['Identifier'].astype('category')
        df_houses.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")
    print("First level of Aggregation is done")
    return output_folder
#-----------------------------------------------

def get_quantile_inputs_from_users():
    message_label = widgets.Label('Please choose values for the 3 hours types')

    # Existing widgets for working, nonworking, and weekend hours
    dropdown_working = widgets.Dropdown(options=['working hours', 'nonworking hours', 'weekends hours'], description='Metric (1)')
    slider_working = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')
    slider_working.style.font_weight = 'bold'
    slider_working.style.font_size = '22px'
    
    dropdown_nonworking = widgets.Dropdown(options=['nonworking hours','working hours', 'weekends hours'], description='Metric (2):')
    slider_nonworking = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')
    slider_nonworking.style.font_weight = 'bold'
    slider_nonworking.style.font_size = '22px'
    
    dropdown_weekend = widgets.Dropdown(options=['weekends hours','working hours', 'nonworking hours'], description='Metric (3)')
    slider_weekend = widgets.IntSlider(value=10, min=0, max=100, step=5, description='Percentile (%)')
    slider_weekend.style.font_weight = 'bold'
    slider_weekend.style.font_size = '22px'
    
    # New widgets for night definition
    dropdown_night_start = widgets.Dropdown(options=list(range(24)), description='Night Start:')
    dropdown_night_end = widgets.Dropdown(options=list(range(24)), description='Night End:')
    dropdown_night_start.style.font_weight = 'bold'
    dropdown_night_start.style.font_size = '22px'
    dropdown_night_end.style.font_weight = 'bold'
    dropdown_night_end.style.font_size = '22px'

    def update_message(*args):
        selected_values = [dropdown_working.value, dropdown_nonworking.value, dropdown_weekend.value]
        if len(set(selected_values)) == 3:
            message_label.value = 'Selection complete. Please also define night hours.'
        else:
            message_label.value = 'Please choose different values for the 3 hours types'

    # Register the event
    dropdown_working.observe(update_message, names='value')
    dropdown_nonworking.observe(update_message, names='value')
    dropdown_weekend.observe(update_message, names='value')

    # Display the widgets
    display(message_label)

    # return the widget objects, need to access their values later
    return (dropdown_working, slider_working, dropdown_nonworking, slider_nonworking, dropdown_weekend, slider_weekend, 
            dropdown_night_start, dropdown_night_end)
#-----------------------------------------------------------------------------------------------------------
def occupancy_status_profile(folder_path, wd):
    """Convert the average occupancy to binary (0 or 1) for each house separately.
    
    Args:
    - folder_path: Path to the folder containing aggregated Parquet files.
    - wd: User-defined quantile values from sliders.

    Returns:
    - folder_path: Path to the folder containing the final processed files.
    """
    print("The final aggregation step just started")
    # Extract the metrics
    metric_values = {
        "working hours": wd[2 * [wd[i].value for i in range(0, 6, 2)].index("working hours") + 1].value,
        "nonworking hours": wd[2 * [wd[i].value for i in range(0, 6, 2)].index("nonworking hours") + 1].value,
        "weekends hours": wd[2 * [wd[i].value for i in range(0, 6, 2)].index("weekends hours") + 1].value
    }
    metric_working = metric_values['working hours'] / 100
    metric_nonworking = metric_values['nonworking hours'] / 100
    metric_weekend = metric_values['weekends hours'] / 100
    night = [wd[-2].value, wd[-1].value]
    progress_bar = widgets.IntProgress(
        value=0, min=0, max=len(os.listdir(folder_path)), 
        description='Processing:', orientation='horizontal')
    display(progress_bar)
    
    # Calculate the metrics for each house
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        df_houses = pd.read_parquet(file_path)
        if 'quantile' in df_houses.columns:
            df_houses= df_houses.drop(['quantile'], axis=1)
        df_houses['date'] = pd.to_datetime(df_houses['date'])
        df_houses['weekday'] = df_houses['date'].dt.weekday
        df_houses['day_type'] = df_houses['weekday'].apply(lambda x: 'weekend' if x >= 5 else 'weekday')
        quantile_data = []
        # For working hours on weekdays
        for hour in range(9, 18):  # From 9 to 17 inclusive
            working_data = df_houses[(df_houses['hour'] == hour) & (df_houses['weekday'] < 5)]
            quantile = working_data['average_occ'].quantile(metric_working)
            quantile_data.append({'hour': hour, 'day_type': 'weekday', 'quantile': quantile, 'type': 'working_hours'})
        # For non-working hours on weekdays
        for hour in list(range(0, 9)) + list(range(18, 24)):  # Before 9 and after 17
            nonworking_data = df_houses[(df_houses['hour'] == hour) & (df_houses['weekday'] < 5)]
            quantile = nonworking_data['average_occ'].quantile(metric_nonworking)
            quantile_data.append({'hour': hour, 'day_type': 'weekday', 'quantile': quantile, 'type': 'nonworking_hours'})
        # For hours during the weekend
        for hour in range(24):  # All day for weekends
            weekend_data = df_houses[(df_houses['hour'] == hour) & (df_houses['weekday'] >= 5)]
            quantile = weekend_data['average_occ'].quantile(metric_weekend)
            quantile_data.append({'hour': hour, 'day_type': 'weekend', 'quantile': quantile, 'type': 'weekend_hours'})
        df_quantile = pd.DataFrame(quantile_data)
        # Compare and convert
        df_final = df_houses.merge(df_quantile, on=['hour', 'day_type'])
        df_final['Occupancy'] = (df_final['average_occ'] >= df_final['quantile']).astype(int)
        # Additional step for night hours
        night_start, night_end = night
        if night_start < night_end:
            night_mask = (df_final['hour'] >= night_start) & (df_final['hour'] <= night_end)
        else:
            night_mask = (df_final['hour'] >= night_start) | (df_final['hour'] <= night_end) 
        night_occupied_mask = df_final.groupby('date')['average_occ'].transform(lambda x: (x > 0).any())
        df_final.loc[night_mask & night_occupied_mask, 'Occupancy'] = 1
        df_final['date_time'] = df_final['date'] + pd.to_timedelta(df_final['hour'], unit='h')
        df_final = df_final.sort_values(by=['Identifier', 'date_time'])
        df_final_leg = df_final[df_final['number_sensors'] >= 2]
        
        columns_order = ['Identifier','date_time', 'date', 'hour'] + [col for col in df_final_leg.columns if col not in ['date_time', 'Identifier', 'date', 'hour']]
        data_reordered = df_final_leg[columns_order]
        data_reordered.reset_index(inplace=True)
        data_reordered = data_reordered.drop(['index', 'weekday', 'type'], axis=1)
        data_reordered = data_reordered.drop_duplicates()
        if data_reordered.empty:
            os.remove(file_path)
        else:
            data_reordered.to_parquet(file_path, index=False, engine="pyarrow", compression="snappy")
        progress_bar.value += 1
    print("The aggregation is done")
    
    return folder_path
#-------------------------------------------------------------------------------------------

import matplotlib.pyplot as plt

def display_results(folder_path):
    """Display aggregated occupancy probability from processed Parquet files."""
    print("Generating results visualization...")
    # Calculate the percentage of 1s (occupied) for each hour
    percentages = []
    house_count = 0
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        df_final = pd.read_parquet(file_path)
        house_count += 1
        house_percentages = df_final.groupby(df_final['date_time'].dt.hour)['Occupancy'].mean()
        percentages.append(house_percentages)
    aggregated_percentages = pd.concat(percentages, axis=1).mean(axis=1)

    plt.figure(figsize=(8, 6))
    plt.plot(aggregated_percentages.index, aggregated_percentages.values, marker='o', linestyle='-', linewidth=2)
    plt.xlabel('Hour of the Day')
    plt.ylabel('Aggregated Occupied Probability')
    plt.title('Aggregated Occupied Probability by Hour of the Day')
    plt.xticks(range(0, 24))
    plt.show()

    print(f"Number of houses analyzed: {house_count}")
    print(f"Average occupied hours: {round(aggregated_percentages.mean() * 100, 2)}%")
#--------------------------------------------------------------------------------------------------

def start(path: str, df_metadata: pd.DataFrame):
    """Pipeline execution to filter, process, and analyze occupancy data interactively.
    
    Args:
    - path: The path to the raw data.
    - df_metadata: The metadata describing the household characteristics.
    
    Returns:
    - Final folder path containing processed occupancy data.
    """
    global wd, output_area
    files, filter_files = get_initial_input_form_user(path, df_metadata)
    if files is None:
        return
    output_folder = filter_sensor_data(files, filter_files)
    output_folder = occupancy_hourly_average(output_folder)
    wd = get_quantile_inputs_from_users()
    # Extract individual widgets from the returned structure if needed
    dropdown_working, slider_working, dropdown_nonworking, slider_nonworking, dropdown_weekend, slider_weekend, dropdown_night_start, dropdown_night_end = wd
    # Define the update_results function
    def update_results(button=None, folder=None):  
        with output_area:
            clear_output(wait=True)
            updated_folder = occupancy_status_profile(folder, wd)  
            display_results(updated_folder) 
    # Create a button that when clicked will run the update_results function
    start_button = widgets.Button(description="Start Analysis")
    start_button.on_click(lambda b: update_results(b, output_folder))
    start_button.style.font_weight = 'bold'
    start_button.style.font_size = '16px'

    # Create an output area for the results if it doesn't exist
    output_area = widgets.Output()

    # Display the message label and widgets
    display(dropdown_working, slider_working)
    display(dropdown_nonworking, slider_nonworking)
    display(dropdown_weekend, slider_weekend)
    display(widgets.HBox([dropdown_night_start, dropdown_night_end]))
    display(start_button, output_area)
