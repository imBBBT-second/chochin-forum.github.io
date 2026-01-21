import base64
import gzip
import sys
import os
import urllib.request
import urllib.parse

# Geometry Dash Constants
# Gamemode Portal IDs
PORTAL_GAMEMODES = {
    12: 'Cube',
    13: 'Ship',
    47: 'Ball',
    111: 'UFO',
    660: 'Wave',
    745: 'Robot',
    1331: 'Spider',
    1933: 'Swing',  # 2.2 Swing
}

# Speed Portal IDs
PORTAL_SPEEDS = {
    200: '0.5x',      # 0.5x (<)
    201: '1x',    # 1x (>)
    202: '2x',      # 2x (>>)
    203: '3x', # 3x (>>>)
    1334: '4x',   # 4x (>>>>)
}

# Speed Values (Units per second, approximate)
# Based on community measurements
SPEED_VALUES = {
    'Slow': 251.16,
    'Normal': 311.58,
    'Fast': 387.42,
    'Very Fast': 468.0,
    'Faster': 576.0,
}

# Mapping between speed names and portal names
PORTAL_NAME_TO_SPEED_NAME = {'0.5x': 'Slow', '1x': 'Normal', '2x': 'Fast', '3x': 'Very Fast', '4x': 'Faster'}
SPEED_NAME_TO_PORTAL_NAME = {v: k for k, v in PORTAL_NAME_TO_SPEED_NAME.items()}

# Start Settings Mappings (from level header)
START_GAMEMODES = {
    0: 'Cube',
    1: 'Ship',
    2: 'Ball',
    3: 'UFO',
    4: 'Wave',
    5: 'Robot',
    6: 'Spider',
    7: 'Swing Copter',
}

START_SPEEDS = {
    0: 'Normal',
    1: 'Slow',
    2: 'Fast',
    3: 'Very Fast',
    4: 'Faster',
}

def decode_level(data):
    """Decodes the Geometry Dash level string (Base64 -> Gzip)."""
    # Fix Base64 padding
    data = data.replace('-', '+').replace('_', '/')
    padding = len(data) % 4
    if padding:
        data += '=' * (4 - padding)

    try:
        decoded = base64.b64decode(data)
        # Try to decompress gzip
        try:
            return gzip.decompress(decoded).decode('utf-8')
        except (gzip.BadGzipFile, ValueError):
            # Might be just base64 encoded without gzip (rare for full levels but possible)
            return decoded.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error decoding level data: {e}")
        return None

def parse_object(obj_str):
    """Parses a single object string into a dictionary."""
    parts = obj_str.split(',')
    obj = {}
    for i in range(0, len(parts) - 1, 2):
        try:
            key = int(parts[i])
            value = parts[i+1]
            obj[key] = value
        except ValueError:
            continue
    return obj

def analyze_level(level_string, level_name="Unknown"):
    """Analyzes the level string and calculates ratios."""
    if not level_string:
        return

    # Split into objects (separated by ;)
    # The first part is the level header settings
    parts = level_string.split(';')
    header_str = parts[0]
    objects_str = parts[1:]

    # Parse Header for start settings
    # Header format is also k,v,k,v...
    header = parse_object(header_str)
    
    # Default Start Settings
    current_gamemode = START_GAMEMODES.get(int(header.get(22, 0)), 'Cube') # kA13 is usually key 22 in raw dict? 
    # Actually in the raw string, keys are kA13 etc. But in the object string part, it's usually k,v.
    # Let's try to find kA13 and kA4 in the raw header string if it's not parsed as ints.
    # The header string usually looks like: kA13,0,kA4,0,...
    
    # Re-parsing header specifically for string keys if needed
    header_parts = header_str.split(',')
    header_dict = {}
    for i in range(0, len(header_parts) - 1, 2):
        header_dict[header_parts[i]] = header_parts[i+1]

    current_gamemode = START_GAMEMODES.get(int(header_dict.get('kA2', 0)), 'Cube')
    current_speed = START_SPEEDS.get(int(header_dict.get('kA4', 0)), 'Normal')
    
    # Check for Platformer Mode (2.2 feature)
    is_platformer = int(header_dict.get('kA22', 0)) == 1
    if is_platformer:
        print("\n[Warning] This is a Platformer Mode level (2.2).")
        print("Time and ratio calculations based on auto-scrolling speed are NOT accurate.\n")

    # Parse Objects
    portals = []
    max_x = 0

    for obj_str in objects_str:
        if not obj_str:
            continue
        
        obj = parse_object(obj_str)
        if 1 not in obj or 2 not in obj: # ID and X are required
            continue
            
        obj_id = int(obj[1])
        x_pos = float(obj[2])
        
        max_x = max(max_x, x_pos)

        if obj_id in PORTAL_GAMEMODES:
            portals.append({'x': x_pos, 'type': 'gamemode', 'value': PORTAL_GAMEMODES[obj_id]})
        elif obj_id in PORTAL_SPEEDS:
            portals.append({'x': x_pos, 'type': 'speed', 'value': PORTAL_SPEEDS[obj_id]})

    # Sort portals by X position
    portals.sort(key=lambda p: p['x'])

    # Calculate Durations
    mode_times = {mode: 0.0 for mode in PORTAL_GAMEMODES.values()}
    speed_times = {speed: 0.0 for speed in PORTAL_SPEEDS.values()}
    
    current_x = 0.0
    total_time = 0.0

    # Add a dummy end portal at the end of the level
    portals.append({'x': max_x, 'type': 'end', 'value': None})

    for p in portals:
        next_x = p['x']
        if next_x > current_x:
            distance = next_x - current_x
            speed_val = SPEED_VALUES[current_speed]
            duration = distance / speed_val
            
            mode_times[current_gamemode] += duration
            
            speed_times_key = SPEED_NAME_TO_PORTAL_NAME.get(current_speed, '1x')
            speed_times[speed_times_key] += duration
            total_time += duration
            
            current_x = next_x
        
        # Update state
        if p['type'] == 'gamemode':
            current_gamemode = p['value']
        elif p['type'] == 'speed':
            current_speed = PORTAL_NAME_TO_SPEED_NAME.get(p['value'], 'Normal')

    # Output Results
    print(f"\n{'='*30}")
    print(f"Total Estimated Time: {total_time:.2f} seconds")
    print(f"Level Name: {level_name}")
    print(f"{'='*30}")
    
    print("\n[Gamemode Ratios]")
    for mode, time in mode_times.items():
        if time > 0:
            ratio = (time / total_time) * 100
            print(f"{mode:<10}: {ratio:6.2f}% ({time:.2f}s)")

    print("\n[Speed Ratios]")
    for speed, time in speed_times.items():
        if time > 0:
            ratio = (time / total_time) * 100
            print(f"{speed:<10}: {ratio:6.2f}% ({time:.2f}s)")
    print(f"{'='*30}\n")

def download_level(level_id):
    """Downloads level data from Geometry Dash servers."""
    print(f"Downloading level {level_id}...")
    url = "http://www.boomlings.com/database/downloadGJLevel22.php"
    params = {
        "levelID": level_id,
        "secret": "Wmfd2893gb7"
    }
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'User-Agent': ''})
    
    try:
        with urllib.request.urlopen(req) as response:
            resp_text = response.read().decode('utf-8')
            
        if resp_text == "-1":
            print("Error: Level not found or download failed.")
            return None
            
        # Parse response (k:v format)
        parts = resp_text.split(':')
        level_data = None
        level_name = "Unknown"
        
        for i in range(0, len(parts), 2):
            if parts[i] == '2':
                level_name = parts[i+1]
            elif parts[i] == '4':
                level_data = parts[i+1]
        
        if level_data:
            return level_name, level_data
            
        print("Error: Level data not found in response.")
        return None
    except Exception as e:
        print(f"Network error: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python auto_ratio.py <level_file.txt or level_id>")
        return

    input_arg = sys.argv[1]
    raw_data = None
    level_name = "Unknown"

    if os.path.exists(input_arg):
        level_name = os.path.basename(input_arg)
        with open(input_arg, 'r') as f:
            raw_data = f.read().strip()
    elif input_arg.isdigit():
        res = download_level(input_arg)
        if res:
            level_name, raw_data = res
    else:
        print("File not found and input is not a valid Level ID.")
        return

    if not raw_data:
        return

    # Check if it looks like a raw object string or needs decoding
    if raw_data.startswith('kS') or raw_data.startswith('kA'):
        # Already decoded string
        analyze_level(raw_data, level_name)
    else:
        # Needs decoding
        decoded = decode_level(raw_data)
        if decoded:
            analyze_level(decoded, level_name)
        else:
            print("Failed to decode level data.")

if __name__ == "__main__":
    main()