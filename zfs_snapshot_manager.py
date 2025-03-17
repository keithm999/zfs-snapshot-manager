#!/usr/bin/env python3
# zfs_snapshot_manager.py

import curses
import subprocess
import os
import re
import time
import argparse
import threading
import json
from datetime import datetime

class ZFSSnapshotManager:
    def __init__(self, stdscr, pools=None):
        self.stdscr = stdscr
        self.pools = pools or self.get_all_pools()
        self.snapshots = []
        self.current_pos = 0
        self.offset = 0
        self.max_rows = 0
        self.max_cols = 0
        self.status_message = ""
        self.status_time = 0
        self.filter_text = ""
        self.is_filtering = False
        self.help_mode = False
        self.loading = False
        self.remote_targets = self.load_remote_targets()
        self.sort_column = 'name'  # Default sort by name
        self.sort_reverse = True   # Default newest first

        # Initialize colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)  # Headers
        curses.init_pair(2, curses.COLOR_GREEN, -1)  # Selected item
        curses.init_pair(3, curses.COLOR_RED, -1)    # Warnings/errors
        curses.init_pair(4, curses.COLOR_YELLOW, -1) # Highlights
        curses.init_pair(5, curses.COLOR_MAGENTA, -1) # Special items

        # Hide cursor
        curses.curs_set(0)

        # Enable mouse events
        curses.mousemask(curses.ALL_MOUSE_EVENTS)

        # Get initial snapshots
        self.refresh_snapshots()

    

    def load_remote_targets(self):
        """Load remote targets from config file"""
        config_dir = os.path.expanduser("~/.config/zfs-snapshot-manager")
        config_file = os.path.join(config_dir, "remote_targets.json")

        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        else:
            # Create default config file
            default_config = []
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config

    def save_remote_targets(self):
        """Save remote targets to config file"""
        config_dir = os.path.expanduser("~/.config/zfs-snapshot-manager")
        config_file = os.path.join(config_dir, "remote_targets.json")

        with open(config_file, 'w') as f:
            json.dump(self.remote_targets, f, indent=2)

    def get_all_pools(self):
        """Get all ZFS pools on the system"""
        try:
            result = subprocess.run(["zpool", "list", "-H", "-o", "name"], 
                                   capture_output=True, text=True, check=True)
            return [line.strip() for line in result.stdout.splitlines()]
        except subprocess.CalledProcessError:
            return []

    def refresh_snapshots(self):
        """Get all snapshots for the specified pools"""
        self.loading = True
        self.draw_screen()

        threading.Thread(target=self._refresh_snapshots_thread).start()

    def _refresh_snapshots_thread(self):
        try:
            snapshots = []
            for pool in self.pools:
                cmd = ["zfs", "list", "-t", "snapshot", "-o", "name,used,refer,creation", "-H", "-r", pool]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.strip().split('\t')
                        if len(parts) == 4:
                            name, used, refer, creation = parts
                            # Parse creation time
                            try:
                                creation_time = datetime.strptime(creation, "%a %b %d %H:%M %Y")
                                creation_str = creation_time.strftime("%Y-%m-%d %H:%M")
                            except ValueError:
                                creation_str = creation

                            snapshots.append({
                                'name': name,
                                'used': used,
                                'refer': refer,
                                'creation': creation_str,
                                'full_creation': creation
                            })

            # Sort snapshots based on current sort settings
            if self.sort_column == 'name':
                self.snapshots = sorted(snapshots, key=lambda x: x['name'], reverse=self.sort_reverse)
            elif self.sort_column == 'used':
                # Convert size strings (like 1K, 2M, 3G) to bytes for proper sorting
                def size_to_bytes(size_str):
                    units = {'B': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
                    if size_str == '-' or size_str == '0':
                        return 0
                    size = float(size_str[:-1])
                    unit = size_str[-1].upper()
                    return int(size * units.get(unit, 1))

                self.snapshots = sorted(snapshots, key=lambda x: size_to_bytes(x['used']), reverse=self.sort_reverse)
            elif self.sort_column == 'refer':
                # Same size conversion for 'refer' column
                self.snapshots = sorted(snapshots, key=lambda x: size_to_bytes(x['refer']), reverse=self.sort_reverse)
            elif self.sort_column == 'creation':
                self.snapshots = sorted(snapshots, key=lambda x: x['full_creation'], reverse=self.sort_reverse)


            # Apply filter if active
            if self.filter_text:
                self.apply_filter()

        except Exception as e:
            self.set_status(f"Error: {str(e)}", error=True)

        self.loading = False
        self.draw_screen()

    def apply_filter(self):
        """Apply filter to snapshots"""
        if not self.filter_text:
            return

        filtered = []
        for snap in self.snapshots:
            if self.filter_text.lower() in snap['name'].lower():
                filtered.append(snap)

        self.snapshots = filtered

    def set_status(self, message, error=False):
        """Set a status message with timestamp"""
        self.status_message = message
        self.status_time = time.time()
        if error:
            self.status_color = curses.color_pair(3)
        else:
            self.status_color = curses.color_pair(4)

    def draw_screen(self):
        """Draw the main interface"""
        self.stdscr.clear()
        self.max_rows, self.max_cols = self.stdscr.getmaxyx()

        # Draw title
        title = "ZFS Snapshot Manager"
        self.stdscr.addstr(0, (self.max_cols - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)

        # Draw pools info
        pools_str = f"Pools: {', '.join(self.pools)}"
        self.stdscr.addstr(1, 0, pools_str, curses.color_pair(1))

        # Draw filter if active
        if self.is_filtering:
            filter_prompt = f"Filter: {self.filter_text}"
            self.stdscr.addstr(1, self.max_cols - len(filter_prompt) - 1, filter_prompt, curses.color_pair(4))

        # Draw help mode or loading indicator
        if self.help_mode:
            self.draw_help()
            return
        elif self.loading:
            loading_text = "Loading snapshots... Please wait."
            self.stdscr.addstr(self.max_rows // 2, (self.max_cols - len(loading_text)) // 2, 
                              loading_text, curses.color_pair(4) | curses.A_BOLD)
            self.stdscr.refresh()
            return

        # Draw column headers
        header_y = 3
        self.stdscr.addstr(header_y, 0, "SNAPSHOT", curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(header_y, 50, "USED", curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(header_y, 60, "REFER", curses.color_pair(1) | curses.A_BOLD)
        self.stdscr.addstr(header_y, 70, "CREATION", curses.color_pair(1) | curses.A_BOLD)

        # Draw column headers with sort indicators
        header_y = 3
        headers = [
            ("SNAPSHOT", 0, 'name'),
            ("USED", 50, 'used'),
            ("REFER", 60, 'refer'),
            ("CREATION", 70, 'creation')
        ]

        for header, pos, col_id in headers:
            # Add sort indicator if this is the sorted column
            if col_id == self.sort_column:
                indicator = "▼" if self.sort_reverse else "▲"
                header = f"{header} {indicator}"

            # Highlight headers to indicate they're clickable
            self.stdscr.addstr(header_y, pos, header, curses.color_pair(1) | curses.A_BOLD)

        # Draw separator
        self.stdscr.addstr(header_y + 1, 0, "─" * (self.max_cols - 1), curses.color_pair(1))

        # Calculate visible items
        visible_rows = self.max_rows - 7  # Account for headers and status

        if not self.snapshots:
            if not self.loading:
                no_snaps = "No snapshots found. Press 'r' to refresh."
                self.stdscr.addstr(self.max_rows // 2, (self.max_cols - len(no_snaps)) // 2, 
                                  no_snaps, curses.color_pair(4))
        else:
            # Adjust offset if needed
            if self.current_pos >= len(self.snapshots):
                self.current_pos = len(self.snapshots) - 1

            if self.current_pos < self.offset:
                self.offset = self.current_pos
            elif self.current_pos >= self.offset + visible_rows:
                self.offset = self.current_pos - visible_rows + 1

            # Draw snapshots
            for i in range(min(visible_rows, len(self.snapshots))):
                if self.offset + i >= len(self.snapshots):
                    break

                snap = self.snapshots[self.offset + i]
                y = header_y + 2 + i

                # Highlight selected item
                if self.offset + i == self.current_pos:
                    attr = curses.color_pair(2) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL

                # Truncate name if needed
                name = snap['name']
                if len(name) > 48:
                    name = name[:45] + "..."

                self.stdscr.addstr(y, 0, name, attr)
                self.stdscr.addstr(y, 50, snap['used'], attr)
                self.stdscr.addstr(y, 60, snap['refer'], attr)
                self.stdscr.addstr(y, 70, snap['creation'], attr)

        # Draw status line
        if self.status_message and time.time() - self.status_time < 5:
            self.stdscr.addstr(self.max_rows - 2, 0, self.status_message, self.status_color)

        # Draw key hints
        help_text = "Press 'h' for help | q:Quit | r:Refresh | d:Show Diff | D:Delete | m:Mount | b:Browse | s:Send | j/k:Up & Down"
        if len(help_text) > self.max_cols:
            help_text = help_text[:self.max_cols-3] + "..."
        self.stdscr.addstr(self.max_rows - 1, 0, help_text, curses.color_pair(1))

        self.stdscr.refresh()

    
    def show_snapshot_diff(self):
        """Show differences between selected snapshot and current dataset state"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            self.set_status("No snapshot selected")
            return

        # Get the selected snapshot (which is a dictionary)
        snap = self.snapshots[self.current_pos]

        # Extract the snapshot name from the dictionary
        snapshot_name = snap['name']  # This is a string like "pool/dataset@snapshot"

        # Extract dataset name from snapshot (everything before the @ symbol)
        dataset = snapshot_name.split('@')[0]

        # Create a temporary file to store the diff output
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, mode='w+t') as temp_file:
            temp_filename = temp_file.name

        # Run the diff command
        try:
            # Use -H for parseable output, -F to show file types
            result = subprocess.run(["sudo", "zfs", "diff", "-FH", snapshot_name, dataset], 
                                capture_output=True, text=True)

            if result.returncode != 0:
                self.set_status(f"Error getting diff: {result.stderr}")
                return

            diff_output = result.stdout

            # If no differences found
            if not diff_output.strip():
                self.set_status("No differences found between snapshot and current state")
                return

            # Format the diff output for better readability
            formatted_output = []
            for line in diff_output.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 3:
                    change_type = parts[0]
                    file_type = parts[1]
                    path = parts[2]

                    # Convert change type symbols to more readable format
                    type_desc = {
                        '-': "Removed",
                        '+': "Added",
                        'M': "Modified",
                        'R': "Renamed"
                    }.get(change_type, change_type)

                    # Convert file type symbols
                    file_desc = {
                        'F': "File",
                        '/': "Directory",
                        '@': "Symlink",
                        'P': "Pipe",
                        '=': "Socket",
                        '>': "Door",
                        '|': "FIFO"
                    }.get(file_type, file_type)

                    formatted_output.append(f"{type_desc} {file_desc}: {path}")

            # Write formatted output to temp file
            with open(temp_filename, 'w') as f:
                f.write(f"Differences between {snapshot_name} and current state:\n\n")
                f.write("\n".join(formatted_output))

            # Temporarily exit curses to show the diff
            curses.endwin()

            # Use less to display the diff with pagination
            subprocess.run(["less", "-R", temp_filename])

            # Restart curses
            self.stdscr.refresh()
            self.draw_screen()

        except Exception as e:
            self.set_status(f"Error: {str(e)}")
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_filename)
            except:
                pass



    def draw_help(self):
        """Draw help screen"""
        help_items = [
            ("Navigation", ""),
            ("  Up/Down", "Navigate through snapshots"),
            ("  Home/End", "Jump to first/last snapshot"),
            ("  PgUp/PgDown", "Page up/down through snapshots"),
            ("", ""),
            ("Actions", ""),
            ("  r", "Refresh snapshot list"),
            ("  /", "Filter snapshots by name"),
            ("  d", "Show differences between snapshot and current state"),
            ("  D", "Delete selected snapshot"),
            ("  m", "Mount selected snapshot"),
            ("  u", "Unmount selected snapshot"),
            ("  b", "Browse snapshot contents"),
            ("  s", "Send snapshot to remote location"),
            ("  a", "Add new remote target"),
            ("", ""),
            ("Other", ""),
            ("  ?", "Show/hide this help"),
            ("  q", "Quit"),
            ("  Click column headers", "Sort by that column"),
        ]

        self.stdscr.clear()
        title = "ZFS Snapshot Manager - Help"
        self.stdscr.addstr(0, (self.max_cols - len(title)) // 2, title, curses.color_pair(1) | curses.A_BOLD)

        for i, (key, desc) in enumerate(help_items):
            if i + 2 >= self.max_rows:
                break

            if not desc:  # This is a section header
                self.stdscr.addstr(i + 2, 2, key, curses.color_pair(1) | curses.A_BOLD)
            else:
                self.stdscr.addstr(i + 2, 2, key, curses.color_pair(4))
                self.stdscr.addstr(i + 2, 20, desc)

        footer = "Press any key to return"
        self.stdscr.addstr(self.max_rows - 1, (self.max_cols - len(footer)) // 2, footer, curses.color_pair(1))
        self.stdscr.refresh()

    def delete_snapshot(self):
        """Delete the currently selected snapshot"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            return

        snap = self.snapshots[self.current_pos]
        name = snap['name']

        # Ask for confirmation
        self.stdscr.addstr(self.max_rows - 3, 0, f"Delete snapshot {name}? (y/n) ", 
                          curses.color_pair(3) | curses.A_BOLD)
        self.stdscr.refresh()

        # Get user input
        while True:
            key = self.stdscr.getch()
            if key in (ord('y'), ord('Y')):
                # Execute deletion
                try:
                    subprocess.run(["zfs", "destroy", name], check=True, capture_output=True)
                    self.set_status(f"Snapshot {name} deleted successfully")
                    # Remove from list
                    self.snapshots.pop(self.current_pos)
                    if self.current_pos >= len(self.snapshots) and len(self.snapshots) > 0:
                        self.current_pos = len(self.snapshots) - 1
                except subprocess.CalledProcessError as e:
                    self.set_status(f"Error deleting snapshot: {e.stderr.decode().strip()}", error=True)
                break
            elif key in (ord('n'), ord('N'), 27):  # n, N or ESC
                break

        # Clear the confirmation line
        self.stdscr.move(self.max_rows - 3, 0)
        self.stdscr.clrtoeol()
        self.draw_screen()

    def mount_snapshot(self):
        """Mount the currently selected snapshot"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            return

        snap = self.snapshots[self.current_pos]
        name = snap['name']

        # Create mount point based on snapshot name
        safe_name = name.replace('/', '_').replace('@', '_')
        mount_point = f"/tmp/zfs_snap_{safe_name}"

        try:
            # Create mount point if it doesn't exist
            if not os.path.exists(mount_point):
                os.makedirs(mount_point)

            # Mount the snapshot
            subprocess.run(["mount", "-t", "zfs", name, mount_point], check=True, capture_output=True)
            self.set_status(f"Snapshot mounted at {mount_point}")
        except subprocess.CalledProcessError as e:
            self.set_status(f"Error mounting snapshot: {e.stderr.decode().strip()}", error=True)
        except OSError as e:
            self.set_status(f"Error creating mount point: {str(e)}", error=True)

        self.draw_screen()

    def unmount_snapshot(self):
        """Unmount a mounted snapshot"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            return

        snap = self.snapshots[self.current_pos]
        name = snap['name']

        # Determine mount point based on snapshot name
        safe_name = name.replace('/', '_').replace('@', '_')
        mount_point = f"/tmp/zfs_snap_{safe_name}"

        try:
            # Check if it's mounted
            result = subprocess.run(["mount"], capture_output=True, text=True)
            if mount_point not in result.stdout:
                self.set_status(f"Snapshot not mounted at {mount_point}", error=True)
                return

            # Unmount
            subprocess.run(["umount", mount_point], check=True, capture_output=True)
            self.set_status(f"Snapshot unmounted from {mount_point}")

            # Try to remove the mount point
            try:
                os.rmdir(mount_point)
            except OSError:
                pass  # Ignore if not empty or other issues

        except subprocess.CalledProcessError as e:
            self.set_status(f"Error unmounting snapshot: {e.stderr.decode().strip()}", error=True)

        self.draw_screen()

    def browse_snapshot(self):
        """Browse the contents of the selected snapshot"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            return

        snap = self.snapshots[self.current_pos]
        name = snap['name']

        # Create temporary mount if needed
        safe_name = name.replace('/', '_').replace('@', '_')
        mount_point = f"/tmp/zfs_snap_{safe_name}"

        mounted = False
        if not os.path.ismount(mount_point):
            try:
                if not os.path.exists(mount_point):
                    os.makedirs(mount_point)
                subprocess.run(["mount", "-t", "zfs", name, mount_point], check=True, capture_output=True)
                mounted = True
            except (subprocess.CalledProcessError, OSError) as e:
                self.set_status(f"Error mounting snapshot: {str(e)}", error=True)
                return

        # Launch file browser
        try:
            # Determine which file browser to use
            browsers = [
                ("ncdu", ["ncdu", mount_point]),
                ("yazi", ["yazi", mount_point]),
                ("mc", ["mc", mount_point]),
                ("ls", ["ls", "-lah", mount_point])
            ]

            for cmd, args in browsers:
                if subprocess.run(["which", cmd], capture_output=True).returncode == 0:
                    # Save terminal state
                    curses.endwin()
                    # Run browser
                    subprocess.run(args)
                    # Restore terminal state
                    curses.doupdate()
                    break
            else:
                self.set_status("No suitable file browser found", error=True)
        finally:
            # Unmount if we mounted it
            if mounted:
                try:
                    subprocess.run(["umount", mount_point], check=True, capture_output=True)
                    try:
                        os.rmdir(mount_point)
                    except OSError:
                        pass
                except subprocess.CalledProcessError:
                    pass

        self.draw_screen()

    def send_snapshot(self):
        """Send snapshot to a remote location"""
        if not self.snapshots or self.current_pos >= len(self.snapshots):
            return

        snap = self.snapshots[self.current_pos]
        name = snap['name']

        if not self.remote_targets:
            self.set_status("No remote targets configured. Use 'a' to add one.", error=True)
            self.draw_screen()
            return

        # Show target selection menu
        self.stdscr.addstr(self.max_rows - 4, 0, "Select destination:", curses.color_pair(1) | curses.A_BOLD)

        for i, target in enumerate(self.remote_targets):
            if i >= 3:  # Show max 3 targets
                break
            self.stdscr.addstr(self.max_rows - 3 + i, 2, f"{i+1}: {target['name']} ({target['host']}:{target['dataset']})")

        self.stdscr.addstr(self.max_rows - 3 + min(len(self.remote_targets), 3), 0, "Enter number or 'c' to cancel: ")
        self.stdscr.refresh()

        # Get user input
        choice = ""
        while True:
            key = self.stdscr.getch()
            if key == ord('c'):
                break
            elif key in range(ord('1'), ord('1') + len(self.remote_targets) + 1):
                choice = chr(key)
                break

        # Clear menu
        for i in range(5):
            self.stdscr.move(self.max_rows - 4 + i, 0)
            self.stdscr.clrtoeol()

        if not choice:
            self.draw_screen()
            return

        # Get selected target
        target_idx = int(choice) - 1
        if target_idx < 0 or target_idx >= len(self.remote_targets):
            self.set_status("Invalid selection", error=True)
            self.draw_screen()
            return

        target = self.remote_targets[target_idx]

        # Execute send command
        self.set_status(f"Sending snapshot to {target['name']}...")
        self.draw_screen()

        try:
            # Build the command
            if target.get('use_ssh', True):
                cmd = [
                    "zfs", "send", name, "|", 
                    "ssh", target['host'], 
                    f"zfs receive -F {target['dataset']}"
                ]
                # Execute with shell=True since we have pipes
                cmd_str = " ".join(cmd)

                # Save terminal state
                curses.endwin()
                print(f"Executing: {cmd_str}")
                print("Transfer in progress... This may take a while.")

                result = subprocess.run(cmd_str, shell=True)

                # Restore terminal state
                curses.doupdate()

                if result.returncode == 0:
                    self.set_status(f"Snapshot sent successfully to {target['name']}")
                else:
                    self.set_status(f"Error sending snapshot. Exit code: {result.returncode}", error=True)
            else:
                # Local send/receive
                cmd = [
                    "zfs", "send", name, "|", 
                    "zfs", "receive", "-F", target['dataset']
                ]
                cmd_str = " ".join(cmd)

                # Save terminal state
                curses.endwin()
                print(f"Executing: {cmd_str}")
                print("Transfer in progress... This may take a while.")

                result = subprocess.run(cmd_str, shell=True)

                # Restore terminal state
                curses.doupdate()

                if result.returncode == 0:
                    self.set_status(f"Snapshot sent successfully to {target['dataset']}")
                else:
                    self.set_status(f"Error sending snapshot. Exit code: {result.returncode}", error=True)

        except Exception as e:
            self.set_status(f"Error sending snapshot: {str(e)}", error=True)

        self.draw_screen()

    def add_remote_target(self):
        """Add a new remote target"""
        # Save terminal state
        curses.endwin()

        print("\n=== Add New Remote Target ===\n")

        name = input("Name (descriptive): ").strip()
        if not name:
            print("Cancelled.")
            curses.doupdate()
            return

        use_ssh = input("Use SSH? (y/n): ").lower().startswith('y')

        if use_ssh:
            host = input("Remote host (user@hostname): ").strip()
            if not host:
                print("Cancelled.")
                curses.doupdate()
                return
        else:
            host = "local"

        dataset = input("Destination dataset: ").strip()
        if not dataset:
            print("Cancelled.")
            curses.doupdate()
            return

        # Add the new target
        new_target = {
            "name": name,
            "host": host,
            "dataset": dataset,
            "use_ssh": use_ssh
        }

        self.remote_targets.append(new_target)
        self.save_remote_targets()

        print(f"\nAdded new target: {name}")
        input("Press Enter to continue...")

        # Restore terminal state
        curses.doupdate()
        self.draw_screen()

    def handle_filter(self):
        """Handle filter input"""
        self.is_filtering = True
        self.filter_text = ""
        self.draw_screen()

        # Show cursor for input
        curses.curs_set(1)

        while True:
            key = self.stdscr.getch()

            if key == 27:  # ESC
                self.is_filtering = False
                break
            elif key == 10:  # Enter
                self.is_filtering = False
                # Apply filter
                self.refresh_snapshots()
                break
            elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace
                if self.filter_text:
                    self.filter_text = self.filter_text[:-1]
            elif 32 <= key <= 126:  # Printable ASCII
                self.filter_text += chr(key)

            # Redraw with updated filter
            self.draw_screen()

        # Hide cursor again
        curses.curs_set(0)
        self.draw_screen()

    def toggle_sort(self, column):
        """Toggle sort column and direction"""
        if self.sort_column == column:
            # Same column, toggle direction
            self.sort_reverse = not self.sort_reverse
        else:
            # New column, set default direction
            self.sort_column = column
            # Default to descending for dates and sizes, ascending for names
            if column in ('creation', 'used', 'refer'):
                self.sort_reverse = True
            else:
                self.sort_reverse = False

        # Re-sort the snapshots
        self.refresh_snapshots()

    

    def run(self):
        """Main loop"""
        self.draw_screen()

        while True:
            key = self.stdscr.getch()

            if key == ord('q'):
                break
            elif key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, _ = curses.getmouse()
                    # Check if click is on header row (row 3)
                    if my == 3:
                        # Determine which column was clicked
                        if 0 <= mx < 50:  # SNAPSHOT column
                            self.toggle_sort('name')
                        elif 50 <= mx < 60:  # USED column
                            self.toggle_sort('used')
                        elif 60 <= mx < 70:  # REFER column
                            self.toggle_sort('refer')
                        elif 70 <= mx < self.max_cols:  # CREATION column
                            self.toggle_sort('creation')
                except curses.error:
                    pass
            elif key == ord('h'):
                self.help_mode = not self.help_mode
            elif key == ord('r'):
                self.refresh_snapshots()
            elif key == ord('/'):
                self.handle_filter()
            elif key == ord('D'):
                self.delete_snapshot()
            elif key == ord('d'): 
                self.show_snapshot_diff()
            elif key == ord('m'):
                self.mount_snapshot()
            elif key == ord('u'):
                self.unmount_snapshot()
            elif key == ord('b'):
                self.browse_snapshot()
            elif key == ord('s'):
                self.send_snapshot()
            elif key == ord('a'):
                self.add_remote_target()
            elif key == curses.KEY_UP or key == ord('k'):
                if self.current_pos > 0:
                    self.current_pos -= 1
            elif key == curses.KEY_DOWN or key == ord('j'):
                if self.snapshots and self.current_pos < len(self.snapshots) - 1:
                    self.current_pos += 1
            elif key == curses.KEY_HOME or key == ord('g'):
                self.current_pos = 0
            elif key == curses.KEY_END or key == ord('G'):
                if self.snapshots:
                    self.current_pos = len(self.snapshots) - 1
            elif key == curses.KEY_PPAGE:  # Page Up
                self.current_pos = max(0, self.current_pos - (self.max_rows - 8))
            elif key == curses.KEY_NPAGE:  # Page Down
                if self.snapshots:
                    self.current_pos = min(len(self.snapshots) - 1, self.current_pos + (self.max_rows - 8))

            if not self.help_mode:
                self.draw_screen()

def main(stdscr, pools=None):
    manager = ZFSSnapshotManager(stdscr, pools)
    manager.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZFS Snapshot Manager TUI")
    parser.add_argument("pools", nargs="*", help="ZFS pools to manage (default: all pools)")
    args = parser.parse_args()

    try:
        curses.wrapper(main, args.pools if args.pools else None)
    except KeyboardInterrupt:
        pass

