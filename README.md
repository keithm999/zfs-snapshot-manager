# ZFS Snapshot Manager

## Features

The ZFS Snapshot Manager TUI includes:

    Listing snapshots: Shows all ZFS snapshots in the selected pools with details:
        Name
        Space used (how much would be reclaimed if deleted)
        Referenced space
        Creation time

    Snapshot management:
        Delete snapshots with confirmation
        Mount/unmount snapshots
        Browse snapshot contents using available file browsers (ncdu, ranger, mc, or ls)
        Send snapshots to remote locations

    Remote target management:
        Configure and save remote targets for snapshot sending
        Support for both SSH and local targets

    Filtering and navigation:
        Filter snapshots by name
        Intuitive keyboard navigation
        Pagination for large snapshot lists

    User interface:
        Color-coded interface for better readability
        Status messages with timeout
        Help screen with keyboard shortcuts

Keyboard Shortcuts

    Navigation:
        Up/Down: Navigate through snapshots
        Home/End: Jump to first/last snapshot
        PgUp/PgDown: Page up/down through snapshots

    Actions:
        r: Refresh snapshot list
        /: Filter snapshots by name
        D: Delete selected snapshot
        d: Show diff between snapshot and current state
        m: Mount selected snapshot
        u: Unmount selected snapshot
        b: Browse snapshot contents
        s: Send snapshot to remote location
        a: Add new remote target

    Other:
        ?: Show/hide help
        q: Quit

## Adding to Nix configuration.nix

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    zfs-snapshot-manager.url = "github:yourusername/zfs-snapshot-manager";
  };

  outputs = { self, nixpkgs, zfs-snapshot-manager, ... }: {
    nixosConfigurations.your-hostname = nixpkgs.lib.nixosSystem {
      # ...
      modules = [
        # ...
        zfs-snapshot-manager.nixosModules.default
        {
          programs.zfs-snapshot-manager.enable = true;
        }
      ];
    };
  };
}
```

## Requirements

The tool requires:

    Python 3.6+
    ZFS utilities installed on the system
    For browsing snapshots: at least one of ncdu, ranger, mc, or ls
    For sending snapshots via SSH: SSH client configured with appropriate access

## Configuration

Remote targets for sending snapshots are stored in ~/.config/zfs-snapshot-manager/remote_targets.json. You can add new
targets through the TUI using the "**a**" key.

Each target has the following properties:

    name: A descriptive name
    host: The remote host (user@hostname) or "local" for local targets
    dataset: The destination dataset
    use_ssh: Boolean indicating whether to use SSH for transfer

## Troubleshooting

If you encounter issues:

    Permission errors: Ensure you have sufficient permissions to manage ZFS. You may need to run the tool with sudo.
    SSH errors: Verify your SSH configuration and ensure you have passwordless access set up.
    Display issues: The TUI is designed for terminals with at least 80x24 dimensions.

For additional help, press ? within the application to view the help screen.
