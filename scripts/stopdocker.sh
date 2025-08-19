#!/bin/bash

SEARCH_TERM="$1"

# Check if a parameter is passed
if [ -z "$SEARCH_TERM" ]; then
    echo "Usage: $0 <search_term>"
    exit 1
# else
#     read -p "Please enter a search term to stop and restart the container: " SEARCH_TERM
fi

# Stop and restart matching containers
docker ps -a | grep "$SEARCH_TERM" | awk '{print $1}' | xargs -I {} bash -c 'docker stop {} '

echo "All containers matching '$SEARCH_TERM' have been stopped "
