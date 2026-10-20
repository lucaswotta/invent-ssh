#!/bin/sh
# Install Invenux for the current user from the extracted release folder, or
# remove it with --uninstall. Nothing is written outside $HOME and no sudo is needed.
set -eu

src=$(cd "$(dirname "$0")" && pwd)
app_dir="$HOME/.local/lib/invenux"
bin_link="$HOME/.local/bin/invenux"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
desktop_file="$data_home/applications/invenux.desktop"
icon_file="$data_home/icons/hicolor/256x256/apps/invenux.png"

refresh_menu() {
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$data_home/applications"
    fi
    if command -v gtk-update-icon-cache >/dev/null; then
        gtk-update-icon-cache -q -t "$data_home/icons/hicolor"
    fi
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -rf "$app_dir"
    rm -f "$bin_link" "$desktop_file" "$icon_file"
    refresh_menu
    echo "Invenux removed. History in $data_home/invenux and reports in Documents/Invenux were kept."
    exit 0
fi

if [ ! -x "$src/invenux" ] || [ ! -d "$src/_internal" ]; then
    echo "Run this script from the extracted invenux-<version>-linux-x86_64 folder." >&2
    exit 1
fi

rm -rf "$app_dir"
mkdir -p "$app_dir" "$(dirname "$bin_link")"
cp -R "$src/invenux" "$src/_internal" "$app_dir/"
ln -sf "$app_dir/invenux" "$bin_link"
install -Dm644 "$src/invenux.png" "$icon_file"
# An absolute Exec keeps the menu entry working when ~/.local/bin is not in PATH.
mkdir -p "$(dirname "$desktop_file")"
sed "s|^Exec=.*|Exec=$app_dir/invenux|" "$src/invenux.desktop" > "$desktop_file"
refresh_menu
echo "Invenux installed in $app_dir. Open it from the applications menu or run: invenux"
