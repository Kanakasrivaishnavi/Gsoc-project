#!/usr/bin/env python3
"""
Check SBO update time on OLS, download new file if newer than local version
"""

import requests
import json
import os
import glob
from datetime import datetime
import time

# Calculate paths relative to script location
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))  # Up two levels to project root
ols_sbo_table_dir = os.path.join(project_root, "ols_sbo_table")


def get_remote_updated_time():
    """Get remote updated time from OLS API"""
    try:
        print("Getting remote update time...")
        response = requests.get(
            "https://www.ebi.ac.uk/ols4/api/ontologies/sbo?lang=en",
            headers={"accept": "application/json"}
        )

        if response.status_code != 200:
            print(f"Failed to get remote update time, status code: {response.status_code}")
            return None

        data = response.json()
        updated_time = data.get('updated')
        print(f"Remote update time: {updated_time}")
        return updated_time

    except Exception as e:
        print(f"Error getting remote update time: {e}")
        return None


def get_local_updated_time():
    """Find the latest updated time from all local JSON files in ols_sbo_table directory"""
    try:
        # Find all SBO-related JSON files in ols_sbo_table directory
        search_pattern = os.path.join(ols_sbo_table_dir, "sbo_*.json")
        json_files = glob.glob(search_pattern)

        if not json_files:
            print("No SBO-related JSON files found")
            return None

        latest_updated = None
        latest_file = None

        # Loop through all files, find the one with the latest updated field
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                file_updated = data.get('metadata', {}).get('updated')
                if file_updated:
                    # Clean timestamp string format
                    def clean_timestamp(ts):
                        if '.' in ts:
                            dt_part, microsec_part = ts.split('.')
                            microsec_part = microsec_part[:6]
                            return f"{dt_part}.{microsec_part}"
                        return ts

                    clean_updated = clean_timestamp(file_updated)
                    file_dt = datetime.fromisoformat(clean_updated)

                    if latest_updated is None or file_dt > latest_updated:
                        latest_updated = file_dt
                        latest_file = json_file

            except Exception as e:
                print(f"Error reading file {json_file}: {e}")
                continue

        if latest_updated:
            print(f"Found latest local file: {latest_file}")
            print(f"Local latest update time: {latest_updated.isoformat()}")
            return latest_updated.isoformat()
        else:
            print("No valid updated time found")
            return None

    except Exception as e:
        print(f"Error reading local file update time: {e}")
        return None


def compare_timestamps(remote_time, local_time):
    """Compare two timestamps, return True if remote time is newer"""
    try:
        # Handle timestamp string format, remove excess microsecond digits
        def clean_timestamp(ts):
            if '.' in ts:
                # Separate datetime and microsecond parts
                dt_part, microsec_part = ts.split('.')
                # Keep only first 6 microsecond digits
                microsec_part = microsec_part[:6]
                return f"{dt_part}.{microsec_part}"
            return ts

        remote_clean = clean_timestamp(remote_time)
        local_clean = clean_timestamp(local_time)

        # Parse timestamp strings
        remote_dt = datetime.fromisoformat(remote_clean)
        local_dt = datetime.fromisoformat(local_clean)

        print(f"Remote time parsed: {remote_dt}")
        print(f"Local time parsed: {local_dt}")

        is_newer = remote_dt > local_dt
        print(f"Is remote time newer: {is_newer}")
        return is_newer

    except Exception as e:
        print(f"Error comparing timestamps: {e}")
        return False


def get_parents_info(parents_link):
    """Get parent label and obo_id from parents link"""
    if not parents_link:
        return []

    try:
        response = requests.get(parents_link, headers={"accept": "application/json"})
        if response.status_code != 200:
            return []

        data = response.json()
        parents = []

        if '_embedded' in data and 'terms' in data['_embedded']:
            for parent in data['_embedded']['terms']:
                parent_info = {
                    'label': parent.get('label'),
                    'obo_id': parent.get('obo_id')
                }
                parents.append(parent_info)

        return parents
    except Exception as e:
        print(f"Error getting parent information: {e}")
        return []


def download_sbo_data():
    """Download complete SBO data"""
    print("Starting to download SBO data...")

    # Get metadata
    metadata_response = requests.get(
        "https://www.ebi.ac.uk/ols4/api/ontologies/sbo?lang=en",
        headers={"accept": "application/json"}
    )

    if metadata_response.status_code != 200:
        print("Failed to get metadata")
        return None

    metadata_data = metadata_response.json()
    metadata = {
        'updated': metadata_data['updated'],
        'version': metadata_data['version'],
        'numberOfTerms': metadata_data['numberOfTerms'],
        'terms_href': metadata_data['_links']['terms']['href']
    }

    # Get all terms
    all_terms = []
    url = "https://www.ebi.ac.uk/ols4/api/ontologies/sbo/terms"
    params = {'size': 100, 'page': 0}

    while True:
        print(f"Getting page {params['page'] + 1} terms...")
        response = requests.get(url, params=params, headers={"accept": "application/json"})

        if response.status_code != 200:
            print(f"Request failed, status code: {response.status_code}")
            break

        data = response.json()

        if '_embedded' in data and 'terms' in data['_embedded']:
            for term in data['_embedded']['terms']:
                # Get parents link
                parents_link = None
                if '_links' in term and 'parents' in term['_links']:
                    parents_link = term['_links']['parents']['href']

                # Get parent information
                parents_info = get_parents_info(parents_link)

                term_data = {
                    'description': term.get('description', []),
                    'label': term.get('label'),
                    'iri': term.get('iri'),
                    'obo_id': term.get('obo_id'),
                    'is_obsolete': term.get('is_obsolete', False),
                    'parents_link': parents_link,
                    'parents': parents_info
                }
                all_terms.append(term_data)

                # Add small delay
                time.sleep(0.05)
        else:
            break

        if 'next' not in data.get('_links', {}):
            break
        params['page'] += 1

    # Combine complete data
    complete_data = {
        'metadata': metadata,
        'terms': all_terms,
        'summary': {
            'total_terms_fetched': len(all_terms),
            'terms_with_parents': len([t for t in all_terms if t['parents']]),
            'terms_without_parents': len([t for t in all_terms if not t['parents']])
        }
    }

    return complete_data


def main():
    """Main function"""
    print("=" * 60)
    print("SBO Data Update Checker")
    print("=" * 60)

    # 1. Get remote update time
    remote_updated = get_remote_updated_time()
    if not remote_updated:
        print("Unable to get remote update time, program exiting")
        return

    # 2. Get local update time
    local_updated = get_local_updated_time()

    # 3. Compare times
    if local_updated is None:
        print("Local file does not exist, will download new file")
        should_download = True
    else:
        should_download = compare_timestamps(remote_updated, local_updated)

    if not should_download:
        print("Local file is already up to date, no download needed")
        return

    print("\n" + "=" * 60)
    print("Update detected, starting to download new data...")
    print("=" * 60)

    # 4. Download new data
    new_data = download_sbo_data()
    if not new_data:
        print("Download failed")
        return

    # 5. Save new file, using updated time for naming
    updated_time = new_data['metadata']['updated']
    # Clean time string for filename
    safe_time = updated_time.replace(':', '-').replace('.', '-')
    filename = os.path.join(ols_sbo_table_dir, f"sbo_data_updated_{safe_time}.json")
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

    print(f"\nNew data saved to: {filename}")
    print(f"Data summary:")
    print(f"  Update time: {updated_time}")
    print(f"  Version: {new_data['metadata']['version']}")
    print(f"  Number of terms: {new_data['summary']['total_terms_fetched']}")
    print(f"  Terms with parents: {new_data['summary']['terms_with_parents']}")
    print(f"  Terms without parents: {new_data['summary']['terms_without_parents']}")


if __name__ == "__main__":
    main()