{
  description = "ZFS Snapshot Manager TUI";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # Python environment with dependencies
        pythonEnv = pkgs.python3.withPackages (
          ps: with ps; [
            # Add your Python dependencies here
            # For example: textual, rich, etc.
          ]
        );
        zfs-snapshot-manager = pkgs.writeScriptBin "zfs-snapshot-manager" ''
          #!${pkgs.python3}/bin/python3
          ${builtins.readFile ./zfs_snapshot_manager.py}
        '';
      in
      {
        packages = {
          default = zfs-snapshot-manager;
          zfs-snapshot-manager = zfs-snapshot-manager;
        };
        apps = {
          default = {
            type = "app";
            program = "${zfs-snapshot-manager}/bin/zfs-snapshot-manager";
          };
        };
        # Development shell with Python and Nix LSP tools for Neovim
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python and dependencies
            pythonEnv
            # Python development tools
            python3Packages.black # Formatter
            python3Packages.isort # Import sorter
            python3Packages.flake8 # Linter
            python3Packages.pylint # Linter
            python3Packages.mypy # Type checker
            # Python LSP servers for Neovim
            pyright # Python LSP
            python3Packages.python-lsp-server # Alternative Python LSP
            vimPlugins.coc-pyright # Coc plugin for Pyright
            # Additional Python tools
            python3Packages.pytest # Testing
            # Nix development tools
            nixpkgs-fmt # Nix formatter
            statix # Nix linter
            deadnix # Find dead/unused Nix code
            # Nix LSP server for Neovim
            nil # Nix LSP
            nixd
            # General development tools
            alejandra # Alternative Nix formatter
          ];
          shellHook = ''
            echo "ZFS Snapshot Manager development environment"
            echo ""
            echo "Python tools:"
            echo " - pyright, python-lsp-server (LSP servers)"
            echo " - black (formatter)"
            echo " - isort (import sorter)"
            echo " - flake8, pylint (linters)"
            echo " - mypy (type checker)"
            echo " - pytest (testing)"
            echo ""
            echo "Nix tools:"
            echo " - nil (LSP server)"
            echo " - nixpkgs-fmt, alejandra (formatters)"
            echo " - statix (linter)"
            echo " - deadnix (dead code finder)"
          '';
        };
        nixosModules.default =
          {
            config,
            lib,
            pkgs,
            ...
          }:
          with lib;
          let
            cfg = config.programs.zfs-snapshot-manager;
          in
          {
            options.programs.zfs-snapshot-manager = {
              enable = mkEnableOption "ZFS Snapshot Manager TUI";
            };
            config = mkIf cfg.enable {
              environment.systemPackages = [ self.packages.${system}.zfs-snapshot-manager ];
            };
          };
      }
    ) // {
    # Add this to make the module available at the top level
    nixosModules.default = { config, lib, pkgs, ... }:
      with lib;
      let
        cfg = config.programs.zfs-snapshot-manager;
      in
      {
        options.programs.zfs-snapshot-manager = {
          enable = mkEnableOption "ZFS Snapshot Manager TUI";
        };

        config = mkIf cfg.enable {
          environment.systemPackages = [ self.packages.${pkgs.system}.zfs-snapshot-manager ];
        };
      };
    };
}
