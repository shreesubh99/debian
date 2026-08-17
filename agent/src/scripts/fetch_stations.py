import os
import csv
import httpx

def fetch_and_save_stations():
    url = "https://raw.githubusercontent.com/datameet/railways/master/stations.json"
    output_file = "indian_railway_stations.csv"
    
    print(f"Downloading station data from {url}...")
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    
    features = data.get("features", [])
    print(f"Found {len(features)} stations in GeoJSON dataset.")
    
    # Define CSV column headers
    headers = ["station_code", "station_name", "state", "zone", "address", "latitude", "longitude"]
    
    rows_written = 0
    with open(output_file, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            
            code = str(props.get("code") or "").strip()
            name = str(props.get("name") or "").strip()
            state = str(props.get("state") or "").strip()
            zone = str(props.get("zone") or "").strip()
            address = str(props.get("address") or "").strip()
            
            # Extract coordinates if geometry is present
            lat = ""
            lon = ""
            if geom and geom.get("type") == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2:
                    lon = coords[0]
                    lat = coords[1]
            
            # Avoid writing completely empty rows
            if not code and not name:
                continue
                
            writer.writerow([code, name, state, zone, address, lat, lon])
            rows_written += 1
            
    print(f"Successfully saved {rows_written} stations to '{output_file}'.")

if __name__ == "__main__":
    fetch_and_save_stations()
