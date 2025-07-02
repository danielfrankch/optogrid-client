import pandas as pd
import numpy as np

def trim_calibration_data(input_file, output_file, target_points=200):
    """
    Trim calibration data to essential points for faster loading
    
    Args:
        input_file: Path to original calibration file
        output_file: Path to save trimmed file
        target_points: Target number of data points (default 200)
    """
    
    # Read the original data
    print(f"Loading {input_file}...")
    data = pd.read_csv(input_file)
    print(f"Original data: {len(data)} points")
    
    # Extract magnetometer data
    mag_x = data['mag_x'].values
    mag_y = data['mag_y'].values
    mag_z = data['mag_z'].values
    
    # Find the range for each axis
    mag_x_range = np.max(mag_x) - np.min(mag_x)
    mag_y_range = np.max(mag_y) - np.min(mag_y)
    mag_z_range = np.max(mag_z) - np.min(mag_z)
    
    print(f"Mag X range: {np.min(mag_x)} to {np.max(mag_x)} (range: {mag_x_range})")
    print(f"Mag Y range: {np.min(mag_y)} to {np.max(mag_y)} (range: {mag_y_range})")
    print(f"Mag Z range: {np.min(mag_z)} to {np.max(mag_z)} (range: {mag_z_range})")
    
    # Strategy 1: Keep points that represent extremes and good distribution
    important_indices = set()
    
    # Add extreme points for each axis
    important_indices.add(np.argmin(mag_x))  # Min X
    important_indices.add(np.argmax(mag_x))  # Max X
    important_indices.add(np.argmin(mag_y))  # Min Y
    important_indices.add(np.argmax(mag_y))  # Max Y
    important_indices.add(np.argmin(mag_z))  # Min Z
    important_indices.add(np.argmax(mag_z))  # Max Z
    
    # Add points at regular intervals to ensure good distribution
    interval = len(data) // (target_points - 20)  # Reserve 20 for extremes
    for i in range(0, len(data), interval):
        important_indices.add(i)
    
    # Add some points that represent good spread in 3D space
    # Calculate distance from center for each point
    center_x = (np.min(mag_x) + np.max(mag_x)) / 2
    center_y = (np.min(mag_y) + np.max(mag_y)) / 2
    center_z = (np.min(mag_z) + np.max(mag_z)) / 2
    
    distances = np.sqrt((mag_x - center_x)**2 + (mag_y - center_y)**2 + (mag_z - center_z)**2)
    
    # Add points with various distances from center
    sorted_indices = np.argsort(distances)
    for i in range(0, len(sorted_indices), len(sorted_indices) // 50):
        important_indices.add(sorted_indices[i])
    
    # Convert to sorted list and limit to target
    important_indices = sorted(list(important_indices))[:target_points]
    
    # Create trimmed dataset
    trimmed_data = data.iloc[important_indices].copy()
    
    # Verify we still have good range coverage
    trimmed_mag_x = trimmed_data['mag_x'].values
    trimmed_mag_y = trimmed_data['mag_y'].values
    trimmed_mag_z = trimmed_data['mag_z'].values
    
    print(f"\nTrimmed data: {len(trimmed_data)} points")
    print(f"Trimmed Mag X range: {np.min(trimmed_mag_x)} to {np.max(trimmed_mag_x)}")
    print(f"Trimmed Mag Y range: {np.min(trimmed_mag_y)} to {np.max(trimmed_mag_y)}")
    print(f"Trimmed Mag Z range: {np.min(trimmed_mag_z)} to {np.max(trimmed_mag_z)}")
    
    # Calculate how much of the original range we preserved
    x_coverage = (np.max(trimmed_mag_x) - np.min(trimmed_mag_x)) / mag_x_range * 100
    y_coverage = (np.max(trimmed_mag_y) - np.min(trimmed_mag_y)) / mag_y_range * 100
    z_coverage = (np.max(trimmed_mag_z) - np.min(trimmed_mag_z)) / mag_z_range * 100
    
    print(f"Range coverage: X={x_coverage:.1f}%, Y={y_coverage:.1f}%, Z={z_coverage:.1f}%")
    
    # Save trimmed data
    trimmed_data.to_csv(output_file, index=False)
    print(f"Saved trimmed calibration to: {output_file}")
    
    return trimmed_data

# Run the trimming
if __name__ == "__main__":
    input_file = "data/OptoGrid 1 Caliberation.csv"
    output_file = "data/OptoGrid 1 Caliberation_trimmed.csv"
    
    trimmed_data = trim_calibration_data(input_file, output_file, target_points=150)
    
    print("\nTrimming complete!")
    print(f"Original size: 1909 points")
    print(f"Trimmed size: {len(trimmed_data)} points")
    print(f"Size reduction: {(1 - len(trimmed_data)/1909)*100:.1f}%")