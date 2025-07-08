import requests
import os
import json
import re
import subprocess
import tempfile
from datetime import datetime


class GitHubFileUpdater:
    def __init__(self, url, repo_owner, repo_name, file_path, branch="master"):
        """
        Initialize GitHub file updater
        
        Description:
            Sets up a GitHubFileUpdater instance to manage downloading, updating, and versioning
            of files from a GitHub repository. Automatically finds the latest local file version.
        
        Input:
            url (str): Raw download link for the file from GitHub
            repo_owner (str): GitHub repository owner/organization name
            repo_name (str): GitHub repository name
            file_path (str): File path within the repository
            branch (str, optional): Git branch name (default: "master")
        
        Output:
            None (constructor)
        """
        self.url = url
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.file_path = file_path
        self.branch = branch
        self.base_filename = os.path.basename(file_path)
        self.local_filename = self._find_latest_local_file()
        self.info_file = f"{self.local_filename}.update_info" if self.local_filename else f"{self.base_filename}.update_info"

    def _find_latest_local_file(self):
        """
        Find the latest local file with timestamp
        
        Description:
            Searches for local files with timestamp suffixes and returns the most recent one.
            Filters out converted files and focuses on original timestamped files.
        
        Input:
            None (uses self.base_filename)
        
        Output:
            str or None: Path to the latest timestamped file, or None if no timestamped files found
        """
        import glob
        
        # Construct filename pattern: SBO_OBO_*.test_obo_json_update
        file_extension = os.path.splitext(self.base_filename)[1]
        file_basename = os.path.splitext(self.base_filename)[0]
        pattern = f"{file_basename}_*{file_extension}"
        
        # Find all matching files
        matching_files = glob.glob(pattern)
        
        if matching_files:
            # Filter out _converted.test_obo_json_update files, keep only original timestamp files
            original_files = [f for f in matching_files if not f.endswith('_converted.test_obo_json_update')]
            
            if original_files:
                # Sort by timestamp in filename (filename format: SBO_OBO_YYYYMMDD_HHMMSS.test_obo_json_update)
                # This sorting finds the latest timestamp file
                original_files.sort(reverse=True)
                return original_files[0]
        
        # If no timestamped file found, check if there's a file with original filename
        if os.path.exists(self.base_filename):
            return self.base_filename
            
        return None

    def get_remote_file_info(self):
        """
        Get latest commit information for the file from GitHub API
        
        Description:
            Retrieves the most recent commit information for the specified file from GitHub's API.
            Used to determine if the remote file has been updated since the last local download.
        
        Input:
            None (uses instance attributes: repo_owner, repo_name, file_path, branch)
        
        Output:
            dict or None: Dictionary containing commit info (sha, last_modified, message, author, url)
                         or None if API call fails or file not found
        """
        api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/commits"

        # Query parameters: only get latest commits affecting the specified file
        params = {
            'path': self.file_path,
            'sha': self.branch,
            'per_page': 1
        }

        try:
            print(f"Checking remote file updates: {self.file_path}")
            response = requests.get(api_url, params=params)

            # Check if API call was successful
            if response.status_code == 403:
                print("GitHub API rate limit exceeded, please try again later")
                return None
            elif response.status_code == 404:
                print("File or repository does not exist")
                return None

            response.raise_for_status()

            commits = response.json()
            if commits:
                latest_commit = commits[0]
                print(f"Remote repository latest update time: {latest_commit['commit']['committer']['date']}")
                return {
                    'sha': latest_commit['sha'],
                    'last_modified': latest_commit['commit']['committer']['date'],
                    'message': latest_commit['commit']['message'],
                    'author': latest_commit['commit']['author']['name'],
                    'url': latest_commit['html_url']
                }
            else:
                print("No commit records found for the file")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Failed to get remote file information: {e}")
            return None

    def load_local_info(self):
        """
        Load locally saved file information
        
        Description:
            Reads the local .update_info file containing metadata about the last download,
            including commit SHA and timestamps for comparison with remote versions.
        
        Input:
            None (uses self.info_file path)
        
        Output:
            dict or None: Dictionary containing local file metadata or None if file doesn't exist or is corrupted
        """
        if os.path.exists(self.info_file):
            try:
                with open(self.info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print(f"Failed to read local info file: {self.info_file}")
                return None
        return None

    def save_local_info(self, info):
        """
        Save file information to local
        
        Description:
            Saves file metadata to a local .update_info file for future comparison.
            Adds local update timestamp to the provided information.
        
        Input:
            info (dict): File information dictionary containing commit details
        
        Output:
            None (saves to self.info_file)
        """
        try:
            info['local_update_time'] = datetime.now().isoformat()
            with open(self.info_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Failed to save local info: {e}")

    def download_file(self):
        """
        Download file
        
        Description:
            Downloads the file directly from the remote URL and saves it with a timestamp.
            Creates backup if file already exists and updates instance attributes.
        
        Input:
            None (uses self.url)
        
        Output:
            bool: True if download successful, False otherwise
        """
        try:
            # Get remote file information to get latest commit time
            remote_info = self.get_remote_file_info()
            if remote_info:
                # Create timestamp from commit date
                commit_date = datetime.fromisoformat(remote_info['last_modified'].replace('Z', '+00:00'))
                timestamp = commit_date.strftime('%Y%m%d_%H%M%S')
                
                # Construct filename with timestamp (using base filename)
                file_extension = os.path.splitext(self.base_filename)[1]
                file_basename = os.path.splitext(self.base_filename)[0]
                timestamped_filename = f"{file_basename}_{timestamp}{file_extension}"
            else:
                # If unable to get remote info, use current time as timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_extension = os.path.splitext(self.base_filename)[1]
                file_basename = os.path.splitext(self.base_filename)[0]
                timestamped_filename = f"{file_basename}_{timestamp}{file_extension}"

            print(f"Downloading file: {timestamped_filename}")
            response = requests.get(self.url)
            response.raise_for_status()

            # Create backup (if file already exists)
            if os.path.exists(timestamped_filename):
                backup_name = f"{timestamped_filename}.backup"
                os.rename(timestamped_filename, backup_name)
                print(f"Backup file created: {backup_name}")

            # Save new file
            with open(timestamped_filename, 'wb') as f:
                f.write(response.content)

            print(f"File downloaded successfully: {timestamped_filename}")
            
            # Update instance filename for subsequent use
            self.local_filename = timestamped_filename
            self.info_file = f"{timestamped_filename}.update_info"
            
            return True

        except requests.exceptions.RequestException as e:
            print(f"Failed to download file: {e}")
            return False

    def check_and_update(self, show_changes=True):
        """
        Check if file has updates, if yes download to temporary location, compare changes, let user decide whether to apply
        
        Description:
            Main method that orchestrates the update process. Checks for remote updates,
            downloads to temporary location, compares changes, and handles user interaction.
        
        Input:
            show_changes (bool, optional): Whether to display detailed change information (default: True)
        
        Output:
            bool: True if update check completed successfully (regardless of whether update was applied),
                  False if errors occurred during the process
        """
        # Get remote file information
        remote_info = self.get_remote_file_info()
        if remote_info is None:
            print("Unable to get remote file information, skipping update check")
            return False

        # Load local file information
        local_info = self.load_local_info()

        # Determine if update is needed
        need_update = False

        if self.local_filename is None:
            print("No local file, starting to download latest file from remote repository")
            need_update = True
        elif not os.path.exists(self.local_filename):
            print("Local file does not exist, need to download")
            need_update = True
        elif local_info is None:
            print("No local update record, need to download")
            need_update = True
        elif local_info.get('sha') != remote_info['sha']:
            print("File update found!")
            print(f"  Local update time: {local_info.get('last_modified', 'Unknown')}")
            print(f"  Remote update time: {remote_info['last_modified']}")
            print(f"  Commit message: {remote_info['message']}")
            print(f"  Commit author: {remote_info['author']}")
            need_update = True
        else:
            print(f"  Remote repository last update time: {remote_info['last_modified']}")
            print(f"  Local file last update time: {local_info.get('last_modified', 'Unknown')}")
            print("✓ File is already the latest version")

        # If update is needed, execute new update process
        if need_update:
            return self._handle_update_with_comparison(remote_info, local_info, show_changes)

        return True
    
    def _handle_update_with_comparison(self, remote_info, local_info, show_changes=True):
        """
        Handle update process with comparison functionality
        
        Description:
            Manages the complete update workflow: downloads to temp location, converts and validates,
            compares changes, prompts user for confirmation, and applies updates if approved.
        
        Input:
            remote_info (dict): Remote file commit information
            local_info (dict or None): Local file metadata
            show_changes (bool, optional): Whether to show change details (default: True)
        
        Output:
            bool: True if update process completed successfully, False if errors or user cancellation
        """
        # Step 1: Download to temporary location
        temp_file = self._download_to_temp(remote_info)
        if not temp_file:
            print("❌ Failed to download temporary file")
            return False
        
        try:
            # Step 2: Convert and validate temporary file
            temp_json = self._convert_and_validate_temp(temp_file)
            if not temp_json:
                print("❌ Temporary file conversion validation failed")
                self._cleanup_temp_files([temp_file])
                return False
            
            # Step 3: Compare changes (if local file exists)
            changes = None
            if self.local_filename and os.path.exists(self.local_filename):
                local_json = self._ensure_local_json()
                if local_json:
                    changes = compare_json_files(local_json, temp_json)
                    
                    if changes and show_changes:
                        # Display change summary
                        from change_logger import ChangeLogger
                        logger = ChangeLogger()
                        logger.display_change_summary(changes)
                        
                        if changes.get('has_changes'):
                            logger.display_detailed_changes(changes, limit=3)
            
            # Step 4: Ask user whether to apply update
            if changes and changes.get('has_changes'):
                user_choice = input("\nApply these updates? (y/n): ").strip().lower()
                if user_choice not in ['y', 'yes']:
                    print("❌ User chose not to apply updates")
                    self._cleanup_temp_files([temp_file, temp_json])
                    return False
            elif not changes or not changes.get('has_changes'):
                # No changes or first download
                if self.local_filename:
                    print("📋 No changes found, but remote version is newer, continuing update")
                user_choice = input("\nApply update? (y/n): ").strip().lower()
                if user_choice not in ['y', 'yes']:
                    print("❌ User chose not to apply update")
                    self._cleanup_temp_files([temp_file, temp_json])
                    return False
            
            # Step 5: Apply update
            return self._apply_update(temp_file, temp_json, remote_info, changes)
            
        except Exception as e:
            print(f"❌ Update process error: {e}")
            temp_files = [temp_file]
            if 'temp_json' in locals() and temp_json:
                temp_files.append(temp_json)
            self._cleanup_temp_files(temp_files)
            return False
    
    def _download_to_temp(self, remote_info):
        """
        Download file to temporary location
        
        Description:
            Downloads the remote file to a temporary location for validation and comparison
            before deciding whether to apply the update.
        
        Input:
            remote_info (dict): Remote file commit information (used for error context)
        
        Output:
            str or None: Path to downloaded temporary file, or None if download failed
        """
        try:
            # Generate temporary filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_extension = os.path.splitext(self.base_filename)[1]
            file_basename = os.path.splitext(self.base_filename)[0]
            temp_filename = f"{file_basename}_temp_{timestamp}{file_extension}"
            
            print(f"🔄 Downloading to temporary location: {temp_filename}")
            response = requests.get(self.url)
            response.raise_for_status()
            
            with open(temp_filename, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Temporary file downloaded successfully: {temp_filename}")
            return temp_filename
            
        except Exception as e:
            print(f"❌ Failed to download temporary file: {e}")
            return None
    
    def _convert_and_validate_temp(self, temp_file):
        """
        Convert temporary OBO file to JSON and perform complete validation
        
        Description:
            Converts the temporary OBO file to JSON format and validates the conversion
            by performing a roundtrip conversion (OBO->JSON->OBO) to ensure data integrity.
        
        Input:
            temp_file (str): Path to the temporary OBO file
        
        Output:
            str or None: Path to generated JSON file if validation successful, None if validation failed
        """
        try:
            base_name = os.path.splitext(temp_file)[0]
            temp_json = f"{base_name}.json"
            temp_converted_obo = f"{base_name}_converted.test_obo_json_update"
            
            print("🔄 Starting temporary file conversion validation process...")
            
            # Step 1: OBO → JSON
            print("1️⃣ Temporary file OBO → JSON")
            data = parse_obo_file(temp_file)
            with open(temp_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Temporary JSON file generated: {temp_json}")
            
            # Step 2: JSON → OBO
            print("2️⃣ Temporary file JSON → OBO")
            convert_json_to_obo(temp_json, temp_converted_obo)
            print(f"✅ Temporary converted OBO file generated: {temp_converted_obo}")
            
            # Step 3: Validate roundtrip conversion
            print("3️⃣ Validate temporary file roundtrip conversion")
            validation_success = validate_roundtrip_conversion(temp_file, temp_converted_obo)
            
            # Clean up conversion file
            if os.path.exists(temp_converted_obo):
                os.remove(temp_converted_obo)
                print(f"🗑️ Cleaned up temporary conversion file: {temp_converted_obo}")
            
            if validation_success:
                print("✅ Temporary file conversion validation passed")
                return temp_json
            else:
                print("❌ Temporary file conversion validation failed")
                if os.path.exists(temp_json):
                    os.remove(temp_json)
                return None
                
        except Exception as e:
            print(f"❌ Temporary file conversion validation failed: {e}")
            # Clean up potentially generated files
            temp_files = [
                f"{os.path.splitext(temp_file)[0]}.json",
                f"{os.path.splitext(temp_file)[0]}_converted.test_obo_json_update"
            ]
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)
            return None
    
    def _ensure_local_json(self):
        """
        Ensure local JSON file exists for comparison
        
        Description:
            Checks if a JSON version of the local file exists. If not, generates one
            from the OBO file to enable detailed comparison with the new version.
        
        Input:
            None (uses self.local_filename)
        
        Output:
            str or None: Path to local JSON file, or None if generation failed
        """
        if not self.local_filename:
            return None
        
        # Check if corresponding JSON file already exists
        base_name = os.path.splitext(self.local_filename)[0]
        local_json = f"{base_name}.json"
        
        if os.path.exists(local_json):
            return local_json
        
        # If not, generate JSON from OBO file
        try:
            print("🔄 Generating JSON for local file for comparison...")
            data = parse_obo_file(self.local_filename)
            
            with open(local_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Local JSON file generated: {local_json}")
            return local_json
            
        except Exception as e:
            print(f"❌ Failed to generate local JSON file: {e}")
            return None
    
    def _apply_update(self, temp_file, temp_json, remote_info, changes):
        """
        Apply update
        
        Description:
            Finalizes the update by moving temporary files to their official locations,
            logging changes, saving update information, and cleaning up old versions.
        
        Input:
            temp_file (str): Path to temporary OBO file
            temp_json (str): Path to temporary JSON file
            remote_info (dict): Remote file commit information
            changes (dict or None): Detected changes between versions
        
        Output:
            bool: True if update applied successfully, False if errors occurred
        """
        try:
            # Generate official filename
            commit_date = datetime.fromisoformat(remote_info['last_modified'].replace('Z', '+00:00'))
            timestamp = commit_date.strftime('%Y%m%d_%H%M%S')
            file_extension = os.path.splitext(self.base_filename)[1]
            file_basename = os.path.splitext(self.base_filename)[0]
            new_filename = f"{file_basename}_{timestamp}{file_extension}"
            new_json_filename = f"{file_basename}_{timestamp}.json"
            
            # Move temporary files to official location
            import shutil
            shutil.move(temp_file, new_filename)
            shutil.move(temp_json, new_json_filename)
            
            # Update instance attributes
            self.local_filename = new_filename
            self.info_file = f"{new_filename}.update_info"
            
            print(f"✅ File updated: {new_filename}")
            print(f"✅ JSON file updated: {new_json_filename}")
            
            # Record change log
            if changes and changes.get('has_changes'):
                from change_logger import ChangeLogger
                logger = ChangeLogger()
                logger.log_changes(changes, None, remote_info)
            
            # Save update information
            self.save_local_info(remote_info)
            
            # Clean up old versions
            self._cleanup_old_versions()
            
            print("🎉 Update completed!")
            return True
                
        except Exception as e:
            print(f"❌ Failed to apply update: {e}")
            return False
    
    def _cleanup_temp_files(self, temp_files):
        """
        Clean up temporary files
        
        Description:
            Removes temporary files created during the update process to avoid
            cluttering the file system.
        
        Input:
            temp_files (list): List of temporary file paths to remove
        
        Output:
            None (files are deleted from filesystem)
        """
        for temp_file in temp_files:
            try:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"🗑️ Cleaned up temporary file: {temp_file}")
            except Exception as e:
                print(f"❌ Failed to clean up temporary file {temp_file}: {e}")
    
    def _cleanup_old_versions(self):
        """
        Keep the latest two timestamp versions, delete the complete file set of the earliest timestamp
        
        Description:
            Manages local file versions by keeping only the latest two timestamp versions
            and removing older versions to prevent excessive disk usage.
        
        Input:
            None (uses self.base_filename to find related files)
        
        Output:
            None (older files are deleted from filesystem)
        """
        import glob
        
        # Construct filename pattern, only match timestamped main files (exclude converted files)
        file_extension = os.path.splitext(self.base_filename)[1]
        file_basename = os.path.splitext(self.base_filename)[0]
        pattern = f"{file_basename}_*{file_extension}"
        
        # Find all matching files, but exclude converted files
        all_files = glob.glob(pattern)
        matching_files = [f for f in all_files if not f.endswith(f'_converted{file_extension}')]
        
        # Count complete file set for each timestamp
        timestamps = set()
        for file in matching_files:
            basename = os.path.splitext(file)[0]
            # Extract timestamp part from filename
            timestamp_part = basename.replace(file_basename + '_', '')
            timestamps.add(timestamp_part)
        
        total_files = len(timestamps) * 4  # 4 files per timestamp
        
        if len(timestamps) <= 2:
            print(f"📁 Currently have {len(timestamps)} timestamp versions (total {total_files} files), no cleanup needed")
            return
        
        # Sort by timestamp (latest first)
        matching_files.sort(key=lambda f: os.path.splitext(f)[0].replace(file_basename + '_', ''), reverse=True)
        
        # Add debug information
        print(f"📁 Found {len(timestamps)} timestamp versions (total {total_files} files), after sorting by timestamp:")
        for i, f in enumerate(matching_files):
            timestamp = os.path.splitext(f)[0].replace(file_basename + '_', '')
            print(f"  {i+1}. {f} (timestamp: {timestamp})")
        
        # Keep the latest two versions
        files_to_keep = matching_files[:2]
        
        # Only delete the earliest timestamp version (i.e., the last file)
        oldest_file = matching_files[-1]
        oldest_basename = os.path.splitext(oldest_file)[0]
        oldest_timestamp = oldest_basename.replace(file_basename + '_', '')
        
        print(f"📁 Keep latest 2 timestamps, delete complete file set of earliest timestamp")
        print(f"🗑️  Will delete timestamp: {oldest_timestamp}")
        
        # Delete complete file set of earliest timestamp
        files_to_delete = [
            oldest_file,  # Main file (.test_obo_json_update)
            f"{oldest_file}.update_info",  # Info file
            f"{oldest_basename}.json",  # JSON file
            f"{oldest_basename}_converted{file_extension}"  # Converted file
        ]
        
        deleted_count = 0
        for file_to_delete in files_to_delete:
            try:
                if os.path.exists(file_to_delete):
                    os.remove(file_to_delete)
                    print(f"🗑️  Deleted file: {file_to_delete}")
                    deleted_count += 1
                    
            except Exception as e:
                print(f"❌ Failed to delete file {file_to_delete}: {e}")
        
        remaining_timestamps = len(timestamps) - 1
        remaining_files = remaining_timestamps * 4
        print(f"✅ Version cleanup completed, deleted {deleted_count} files, remaining {remaining_timestamps} timestamp versions (total {remaining_files} files)")
    

    def get_update_status(self):
        """
        Get file update status information
        
        Description:
            Provides comprehensive status information about local and remote file versions,
            including whether an update is needed.
        
        Input:
            None (uses instance attributes and calls remote API)
        
        Output:
            dict: Status dictionary containing local file existence, remote info availability,
                  update necessity, and version timestamps
        """
        remote_info = self.get_remote_file_info()
        local_info = self.load_local_info()

        status = {
            'local_file_exists': self.local_filename is not None and os.path.exists(self.local_filename),
            'has_local_info': local_info is not None,
            'remote_info_available': remote_info is not None,
            'needs_update': False
        }

        if remote_info:
            if local_info:
                status['needs_update'] = local_info.get('sha') != remote_info['sha']
                status['local_sha'] = local_info.get('sha', '')
                status['local_update_time'] = local_info.get('local_update_time', '')
            else:
                # No local info means we need to update
                status['needs_update'] = True
                status['local_sha'] = False
                status['local_update_time'] = False
            
            status['remote_sha'] = remote_info['sha']
            status['remote_update_time'] = remote_info['last_modified']

        return status


def parse_obo_file(file_path):
    """
    Parse OBO file and convert to JSON structure
    
    Description:
        Parses an OBO (Open Biomedical Ontologies) file and converts it to a structured
        JSON format, preserving header information, terms, and typedefs.
    
    Input:
        file_path (str): Path to the OBO file to parse
    
    Output:
        dict: Structured dictionary containing 'header', 'terms', and optionally 'typedefs'
    """
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into sections by [Term] and [Typedef]
    sections = re.split(r'\[(?:Term|Typedef)\]', content)
    header_part = sections[0].strip()
    
    # Find all section markers
    section_markers = re.findall(r'\[(?:Term|Typedef)\]', content)
    
    # Parse header
    header = {}
    for line in header_part.split('\n'):
        line = line.rstrip()  # Only remove whitespace on the right (including newlines)
        if line.strip() and ':' in line:  # Use strip() to check if empty line and if contains colon
            key, value = line.split(':', 1)
            header[key.strip()] = value.lstrip()  # Only remove spaces on the left, keep spaces on the right
    
    # Parse terms and typedefs
    terms = []
    typedefs = []
    
    for i, section_content in enumerate(sections[1:], 0):
        if i >= len(section_markers):
            break
            
        section_type = section_markers[i]
        parsed_section = {}
        
        # Split content at next section marker to avoid mixing sections
        lines = section_content.split('\n')
        section_lines = []
        
        for line in lines:
            line = line.rstrip('\n')  # Only remove newline characters
            if line.strip().startswith('[') and (line.strip() == '[Term]' or line.strip() == '[Typedef]'):
                break
            section_lines.append(line)
        
        # Parse the section
        for line in section_lines:
            line = line.rstrip('\n')  # Only remove newline characters, keep other spaces
            if line.strip() and ':' in line:  # Use strip() to check if empty line and if contains colon
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.lstrip()  # Only remove spaces on the left, keep spaces on the right
                
                # Handle special cases
                if key == 'is_a':
                    # Extract ID and name from "SBO:0000064 ! mathematical expression"
                    match = re.match(r'(SBO:\d+)\s*!\s*(.*)', value)
                    if match:
                        if key not in parsed_section:
                            parsed_section[key] = []
                        parsed_section[key].append({
                            'id': match.group(1),
                            'name': match.group(2)
                        })
                    else:
                        if key not in parsed_section:
                            parsed_section[key] = []
                        parsed_section[key].append(value)
                elif key == 'relationship':
                    # Handle relationship entries
                    if key not in parsed_section:
                        parsed_section[key] = []
                    parsed_section[key].append(value)
                else:
                    # Handle regular key-value pairs
                    if key in parsed_section:
                        # Convert to list if multiple values
                        if not isinstance(parsed_section[key], list):
                            parsed_section[key] = [parsed_section[key]]
                        parsed_section[key].append(value)
                    else:
                        parsed_section[key] = value
        
        if parsed_section:  # Only add non-empty sections
            if section_type == '[Term]':
                terms.append(parsed_section)
            elif section_type == '[Typedef]':
                typedefs.append(parsed_section)
    
    result = {
        'header': header,
        'terms': terms
    }
    
    if typedefs:
        result['typedefs'] = typedefs
    
    return result


def convert_json_to_obo(json_file, obo_file):
    """
    Convert JSON file back to OBO format
    
    Description:
        Converts a JSON-structured ontology file back to standard OBO format,
        maintaining proper field ordering and formatting conventions.
    
    Input:
        json_file (str): Path to the JSON file to convert
        obo_file (str): Path where the output OBO file will be saved
    
    Output:
        None (writes OBO file to specified path)
    """
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    obo_lines = []
    
    # Write header
    header = data.get('header', {})
    for key, value in header.items():
        obo_lines.append(f"{key}: {value}")
    
    obo_lines.append("")  # Empty line after header
    
    # Write terms
    terms = data.get('terms', [])
    for term in terms:
        obo_lines.append("[Term]")
        
        # Write term fields in a specific order for consistency
        field_order = ['id', 'name', 'comment', 'is_a', 'relationship', 'def', 'synonym', 'xref']
        
        # First write ordered fields
        for field in field_order:
            if field in term:
                value = term[field]
                if isinstance(value, list):
                    for v in value:
                        if field == 'is_a' and isinstance(v, dict):
                            # Reconstruct "SBO:0000064 ! mathematical expression" format
                            obo_lines.append(f"{field}: {v['id']} ! {v['name']}")
                        else:
                            obo_lines.append(f"{field}: {v}")
                else:
                    obo_lines.append(f"{field}: {value}")
        
        # Then write any remaining fields not in the order list
        for key, value in term.items():
            if key not in field_order:
                if isinstance(value, list):
                    for v in value:
                        obo_lines.append(f"{key}: {v}")
                else:
                    obo_lines.append(f"{key}: {value}")
        
        obo_lines.append("")  # Empty line after each term
    
    # Write typedefs
    typedefs = data.get('typedefs', [])
    for typedef in typedefs:
        obo_lines.append("[Typedef]")
        
        # Write typedef fields in a specific order
        typedef_field_order = ['id', 'name', 'is_transitive', 'is_symmetric', 'is_asymmetric', 'is_reflexive']
        
        # First write ordered fields
        for field in typedef_field_order:
            if field in typedef:
                value = typedef[field]
                if isinstance(value, list):
                    for v in value:
                        obo_lines.append(f"{field}: {v}")
                else:
                    obo_lines.append(f"{field}: {value}")
        
        # Then write any remaining fields not in the order list
        for key, value in typedef.items():
            if key not in typedef_field_order:
                if isinstance(value, list):
                    for v in value:
                        obo_lines.append(f"{key}: {v}")
                else:
                    obo_lines.append(f"{key}: {value}")
        
        obo_lines.append("")  # Empty line after each typedef
    
    # Write to file
    with open(obo_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(obo_lines))
        # Ensure file ends with newline to maintain consistency with original file
        if obo_lines and obo_lines[-1] == '':
            f.write('\n')  # If last line is already empty, add only one newline
        elif obo_lines:
            f.write('\n')  # If last line is not empty, add one newline


def run_git_diff(file1, file2, options=None):
    """
    Run git diff and return results
    
    Description:
        Executes git diff command to compare two files and returns the output,
        error messages, and return code for analysis.
    
    Input:
        file1 (str): Path to the first file for comparison
        file2 (str): Path to the second file for comparison
        options (list, optional): Additional git diff options (e.g., ['--ignore-all-space'])
    
    Output:
        tuple: (stdout, stderr, returncode) from git diff command
    """
    cmd = ['git', 'diff', '--no-index']
    if options:
        cmd.extend(options)
    cmd.extend([file1, file2])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return None, str(e), 1




def validate_roundtrip_conversion(original_file, reverted_file):
    """
    Verify whether roundtrip conversion is successful (ignore format differences)
    
    Description:
        Validates that OBO->JSON->OBO conversion preserves semantic content by comparing
        the original file with the converted-back file using multiple comparison strategies.
    
    Input:
        original_file (str): Path to the original OBO file
        reverted_file (str): Path to the OBO file converted back from JSON
    
    Output:
        bool: True if semantic content is preserved, False if conversion failed
    """
    print("🔄 Verifying roundtrip conversion...")
    
    # Check if files exist
    if not os.path.exists(original_file):
        print(f"❌ Original file does not exist: {original_file}")
        return False
    
    if not os.path.exists(reverted_file):
        print(f"❌ Converted file does not exist: {reverted_file}")
        return False
    
    # Direct comparison (complete identity is the best case)
    stdout, stderr, code = run_git_diff(original_file, reverted_file)
    if stderr:
        print(f"❌ Git diff error: {stderr}")
        return False
    
    if not stdout or not stdout.strip():
        print("✅ Files are completely identical! Roundtrip conversion successful")
        return True
    
    # Comparison ignoring all whitespace differences
    print("📋 Format differences detected, performing whitespace-ignoring comparison...")
    stdout, stderr, code = run_git_diff(original_file, reverted_file, 
                                       ['--ignore-all-space', '--ignore-blank-lines'])
    
    if stderr:
        print(f"❌ Git diff error: {stderr}")
        return False
    
    if not stdout or not stdout.strip():
        print("✅ Files are identical after ignoring format differences! Roundtrip conversion successful")
        return True
    
    # Semantic content comparison (most lenient comparison)
    print("📋 Still differences found, performing semantic content comparison...")
    semantic_match = validate_semantic_content(original_file, reverted_file)
    
    if semantic_match:
        print("✅ Semantic content is completely consistent! Roundtrip conversion successful (only format differences)")
        return True
    else:
        print("❌ Semantic content is inconsistent! Roundtrip conversion failed")
        return False


def validate_semantic_content(file1, file2):
    """
    Verify whether semantic content of two OBO files is consistent (ignore format)
    
    Description:
        Performs semantic comparison of two OBO files by extracting meaningful content
        lines and comparing them while ignoring formatting differences.
    
    Input:
        file1 (str): Path to the first OBO file
        file2 (str): Path to the second OBO file
    
    Output:
        bool: True if semantic content is identical, False if differences found
    """
    
    def extract_semantic_content(file_path):
        """Extract semantic content from OBO file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract all meaningful lines, ignore empty lines and format
        meaningful_lines = []
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('!'):  # Ignore comment lines
                # Normalize whitespace characters
                line = ' '.join(line.split())
                meaningful_lines.append(line)
        
        return set(meaningful_lines)  # Use set to ignore order
    
    try:
        content1 = extract_semantic_content(file1)
        content2 = extract_semantic_content(file2)
        
        # Compare semantic content
        missing_in_file2 = content1 - content2
        extra_in_file2 = content2 - content1
        
        if missing_in_file2:
            print(f"📋 File2 missing content (first 5): {list(missing_in_file2)[:5]}")
        
        if extra_in_file2:
            print(f"📋 File2 extra content (first 5): {list(extra_in_file2)[:5]}")
        
        return len(missing_in_file2) == 0 and len(extra_in_file2) == 0
        
    except Exception as e:
        print(f"❌ Semantic comparison error: {e}")
        return False


def compare_json_files(old_json_file, new_json_file):
    """
    Compare differences between two JSON files
    
    Description:
        Performs detailed comparison between two JSON-formatted ontology files,
        identifying added, deleted, and modified terms, typedefs, and header fields.
    
    Input:
        old_json_file (str): Path to the old version JSON file
        new_json_file (str): Path to the new version JSON file
        
    Output:
        dict: Comprehensive change report containing header_changes, term_changes,
              typedef_changes, statistics, and has_changes boolean
    """
    try:
        # Read JSON files
        with open(old_json_file, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
        
        with open(new_json_file, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        
        # Compare header
        header_changes = _compare_headers(old_data.get('header', {}), new_data.get('header', {}))
        
        # Compare terms
        term_changes = _compare_terms(old_data.get('terms', []), new_data.get('terms', []))
        
        # Compare typedefs
        typedef_changes = _compare_typedefs(old_data.get('typedefs', []), new_data.get('typedefs', []))
        
        # Count changes
        stats = {
            'terms_added': len(term_changes['added']),
            'terms_deleted': len(term_changes['deleted']),
            'terms_updated': len(term_changes['updated']),
            'typedefs_added': len(typedef_changes['added']),
            'typedefs_deleted': len(typedef_changes['deleted']),
            'typedefs_updated': len(typedef_changes['updated']),
            'header_updated': bool(header_changes)
        }
        
        return {
            'header_changes': header_changes,
            'term_changes': term_changes,
            'typedef_changes': typedef_changes,
            'stats': stats,
            'has_changes': any([
                header_changes,
                term_changes['added'],
                term_changes['deleted'], 
                term_changes['updated'],
                typedef_changes['added'],
                typedef_changes['deleted'],
                typedef_changes['updated']
            ])
        }
        
    except Exception as e:
        print(f"❌ JSON file comparison error: {e}")
        return None


def _compare_headers(old_header, new_header):
    """
    Compare changes in header section
    
    Description:
        Compares header fields between old and new versions, identifying
        added, updated, and deleted fields.
    
    Input:
        old_header (dict): Header fields from old version
        new_header (dict): Header fields from new version
    
    Output:
        dict: Changes dictionary with field names as keys and change details as values
    """
    changes = {}
    
    # Check for added fields
    for key, value in new_header.items():
        if key not in old_header:
            changes[key] = {'action': 'added', 'new_value': value}
        elif old_header[key] != value:
            changes[key] = {'action': 'updated', 'old_value': old_header[key], 'new_value': value}
    
    # Check for deleted fields
    for key, value in old_header.items():
        if key not in new_header:
            changes[key] = {'action': 'deleted', 'old_value': value}
    
    return changes


def _compare_terms(old_terms, new_terms):
    """
    Compare changes in terms section
    
    Description:
        Compares term definitions between versions, identifying added, deleted,
        and modified terms with detailed field-level change tracking.
    
    Input:
        old_terms (list): List of term dictionaries from old version
        new_terms (list): List of term dictionaries from new version
    
    Output:
        dict: Changes organized into 'added', 'deleted', and 'updated' lists
    """
    # Build mapping from ID to term
    old_terms_dict = {term.get('id'): term for term in old_terms if 'id' in term}
    new_terms_dict = {term.get('id'): term for term in new_terms if 'id' in term}
    
    added = []
    deleted = []
    updated = []
    
    # Check for added terms
    for term_id, term in new_terms_dict.items():
        if term_id not in old_terms_dict:
            added.append(term)
    
    # Check for deleted terms
    for term_id, term in old_terms_dict.items():
        if term_id not in new_terms_dict:
            deleted.append(term)
    
    # Check for updated terms
    for term_id in set(old_terms_dict.keys()) & set(new_terms_dict.keys()):
        old_term = old_terms_dict[term_id]
        new_term = new_terms_dict[term_id]
        
        if old_term != new_term:
            # Detailed comparison of field changes
            field_changes = _compare_term_fields(old_term, new_term)
            if field_changes:
                updated.append({
                    'id': term_id,
                    'old_term': old_term,
                    'new_term': new_term,
                    'field_changes': field_changes
                })
    
    return {
        'added': added,
        'deleted': deleted,
        'updated': updated
    }


def _compare_typedefs(old_typedefs, new_typedefs):
    """
    Compare changes in typedefs section
    
    Description:
        Compares typedef definitions between versions, identifying added, deleted,
        and modified typedefs with detailed field-level change tracking.
    
    Input:
        old_typedefs (list): List of typedef dictionaries from old version
        new_typedefs (list): List of typedef dictionaries from new version
    
    Output:
        dict: Changes organized into 'added', 'deleted', and 'updated' lists
    """
    # Build mapping from ID to typedef
    old_typedefs_dict = {typedef.get('id'): typedef for typedef in old_typedefs if 'id' in typedef}
    new_typedefs_dict = {typedef.get('id'): typedef for typedef in new_typedefs if 'id' in typedef}
    
    added = []
    deleted = []
    updated = []
    
    # Check for added typedefs
    for typedef_id, typedef in new_typedefs_dict.items():
        if typedef_id not in old_typedefs_dict:
            added.append(typedef)
    
    # Check for deleted typedefs
    for typedef_id, typedef in old_typedefs_dict.items():
        if typedef_id not in new_typedefs_dict:
            deleted.append(typedef)
    
    # Check for updated typedefs
    for typedef_id in set(old_typedefs_dict.keys()) & set(new_typedefs_dict.keys()):
        old_typedef = old_typedefs_dict[typedef_id]
        new_typedef = new_typedefs_dict[typedef_id]
        
        if old_typedef != new_typedef:
            field_changes = _compare_term_fields(old_typedef, new_typedef)
            if field_changes:
                updated.append({
                    'id': typedef_id,
                    'old_typedef': old_typedef,
                    'new_typedef': new_typedef,
                    'field_changes': field_changes
                })
    
    return {
        'added': added,
        'deleted': deleted,
        'updated': updated
    }


def _compare_term_fields(old_term, new_term):
    """
    Compare field changes of a single term or typedef
    
    Description:
        Performs detailed field-by-field comparison of a single term or typedef,
        identifying which specific fields were added, deleted, or modified.
    
    Input:
        old_term (dict): Term/typedef dictionary from old version
        new_term (dict): Term/typedef dictionary from new version
    
    Output:
        dict: Field changes with field names as keys and change details as values
    """
    changes = {}
    
    # Get all fields
    all_fields = set(old_term.keys()) | set(new_term.keys())
    
    for field in all_fields:
        old_value = old_term.get(field)
        new_value = new_term.get(field)
        
        if old_value != new_value:
            if field not in old_term:
                changes[field] = {'action': 'added', 'new_value': new_value}
            elif field not in new_term:
                changes[field] = {'action': 'deleted', 'old_value': old_value}
            else:
                changes[field] = {'action': 'updated', 'old_value': old_value, 'new_value': new_value}
    
    return changes






