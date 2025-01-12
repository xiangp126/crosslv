#!/bin/bash

source_monaco_ttf="$HOME/myGit/crosslv/fonts/monaco.ttf"
if [ ! -f $source_monaco_ttf ]; then
    echo "Source monaco font does not exist!"
    exit 1
fi

# Create fonts directory if it doesn't exist
mkdir -p $HOME/.local/share/fonts

cp $source_monaco_ttf $HOME/.local/share/fonts/

# Refresh the font cache
fc-cache -f -v
if [ $? -ne 0 ]; then
    echo "Failed to refresh the font cache!"
    exit 1
fi
echo "Monaco font installed successfully!"
