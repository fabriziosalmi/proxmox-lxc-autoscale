#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Function to get total CPU cores using /proc/cpuinfo
get_total_cores() {
  grep -c '^processor' /proc/cpuinfo
}

# Function to get total memory in MB using free command
get_total_memory() {
  free -m | awk '/^Mem:/{print $2}'
}

# Function to get list of running LXC containers
get_running_lxc_containers() {
  pct list | grep running | awk '{print $1}'
}

# Function to get list of stopped LXC containers
get_stopped_lxc_containers() {
  pct list | grep stopped | awk '{print $1}'
}

# Function to get the number of cores for a specific LXC container
get_container_cores() {
  pct config $1 | grep cores | awk '{print $2}'
}

# Function to get the memory allocated to a specific LXC container in MB
get_container_memory() {
  pct config $1 | grep memory | awk '{print $2}'
}

# Function to ask for user confirmation or provide a default value
ask_for_confirmation() {
  local prompt="$1"
  local default_value="$2"
  read -p "💬 $prompt [$default_value]: " input
  echo "${input:-$default_value}"
}

# Modified Function to prompt for containers to ignore
ask_for_ignored_containers() {
  local containers=("$@")
  local ignored=()

  echo "💻 Detected running LXC containers: ${containers[*]}" >&2
  read -p "Enter the IDs of the containers you want to ignore, separated by spaces or commas (e.g., 100,101,102) or press Enter to skip: " ignored_ids

  if [ -n "$ignored_ids" ]; then
    IFS=', ' read -ra ignored_array <<< "$ignored_ids"
    for id in "${ignored_array[@]}"; do
      if [[ "$id" =~ ^[0-9]+$ ]] && [[ " ${containers[*]} " =~ " $id " ]]; then
        ignored+=("$id")
      else
        echo "⚠️  Warning: Container ID $id is either not numeric or not in the list of running containers." >&2
      fi
    done
  fi

  if [ ${#ignored[@]} -eq 0 ]; then
    echo "⚠️ No containers were ignored." >&2
  else
    echo "🚫 Ignored containers: ${ignored[*]}" >&2
  fi

  printf '%s\n' "${ignored[@]}"
}




# Start of the script
echo "🚀 Starting LXC autoscale configuration..."

# Gather system information
total_cores=$(get_total_cores)
total_memory=$(get_total_memory)

# Get lists of running and stopped LXC containers
running_containers=($(get_running_lxc_containers))
stopped_containers=($(get_stopped_lxc_containers))

# Print out the lists of containers
echo "📊 Total containers: $((${#running_containers[@]} + ${#stopped_containers[@]})) (Running: ${#running_containers[@]}, Stopped: ${#stopped_containers[@]})"
echo "🛑 Stopped containers: ${stopped_containers[*]}"
echo "✅ Running containers: ${running_containers[*]}"


# Ask the user which containers to ignore
echo "Preparing to ask about ignored containers..."
mapfile -t ignored_containers < <(ask_for_ignored_containers "${running_containers[@]}")

# Debug output
echo "Debug: Ignored containers: ${ignored_containers[*]}"
echo "Debug: Running containers before filtering: ${running_containers[*]}"

# Filter out ignored containers from the list of LXC containers to process
processed_containers=()
for ctid in "${running_containers[@]}"; do
  if [[ ! " ${ignored_containers[*]} " =~ " $ctid " ]]; then
    processed_containers+=("$ctid")
  fi
done

# Debug output
echo "Debug: Processed containers after filtering: ${processed_containers[*]}"

# If no containers are left after ignoring, exit
if [ ${#processed_containers[@]} -eq 0 ]; then
  echo "❌ No containers left to process after applying ignore list. Exiting..."
  exit 1
fi

# Prepare to calculate the total used resources
total_used_cores=0
total_used_memory=0

# Gather resources for each container
for ctid in "${processed_containers[@]}"; do
  cores=$(get_container_cores $ctid)
  memory=$(get_container_memory $ctid)
  total_used_cores=$((total_used_cores + cores))
  total_used_memory=$((total_used_memory + memory))
done

# Display the total resources used and available
echo "🔍 Total resources on Proxmox host: $total_cores cores, $total_memory MB memory"
echo "🔍 Total resources used by selected containers: $total_used_cores cores, $total_used_memory MB memory"
echo "🔍 Remaining resources: $((total_cores - total_used_cores)) cores, $((total_memory - total_used_memory)) MB memory"

# Ask for confirmation for DEFAULT section settings
poll_interval=$(ask_for_confirmation "Polling interval (seconds)" "600")
cpu_upper_threshold=$(ask_for_confirmation "CPU upper threshold (%)" "85")
cpu_lower_threshold=$(ask_for_confirmation "CPU lower threshold (%)" "10")
memory_upper_threshold=$(ask_for_confirmation "Memory upper threshold (%)" "80")
memory_lower_threshold=$(ask_for_confirmation "Memory lower threshold (%)" "10")
core_min_increment=$(ask_for_confirmation "Minimum core increment" "1")
core_max_increment=$(ask_for_confirmation "Maximum core increment" "4")
memory_min_increment=$(ask_for_confirmation "Minimum memory increment (MB)" "512")
reserve_cpu_percent=$(ask_for_confirmation "Reserved CPU percentage" "10")
reserve_memory_mb=$(ask_for_confirmation "Reserved memory (MB)" "2048")
log_file=$(ask_for_confirmation "Log file path" "/var/log/lxc_autoscale.log")
lock_file=$(ask_for_confirmation "Lock file path" "/var/lock/lxc_autoscale.lock")
backup_dir=$(ask_for_confirmation "Backup directory" "/var/lib/lxc_autoscale/backups")
off_peak_start=$(ask_for_confirmation "Off-peak start hour" "22")
off_peak_end=$(ask_for_confirmation "Off-peak end hour" "6")
energy_mode=$(ask_for_confirmation "Enable energy-saving mode (True/False)" "False")
behaviour=$(ask_for_confirmation "Behaviour (normal/conservative/aggressive)" "normal")

# Prepare YAML content
yaml_content="DEFAULT:
  poll_interval: $poll_interval
  cpu_upper_threshold: $cpu_upper_threshold
  cpu_lower_threshold: $cpu_lower_threshold
  memory_upper_threshold: $memory_upper_threshold
  memory_lower_threshold: $memory_lower_threshold
  core_min_increment: $core_min_increment
  core_max_increment: $core_max_increment
  memory_min_increment: $memory_min_increment
  reserve_cpu_percent: $reserve_cpu_percent
  reserve_memory_mb: $reserve_memory_mb
  log_file: $log_file
  lock_file: $lock_file
  backup_dir: $backup_dir
  off_peak_start: $off_peak_start
  off_peak_end: $off_peak_end
  energy_mode: $energy_mode
  behaviour: $behaviour
  ignore_lxc: 
$(printf '    - %s\n' "${ignored_containers[@]}")
"

# Generate TIER_ sections for each processed LXC container
echo "⚙️  Configuring TIER sections..."
for ctid in "${processed_containers[@]}"; do
  cores=$(get_container_cores $ctid)
  memory=$(get_container_memory $ctid)

  tier_cpu_upper_threshold=$(ask_for_confirmation "CPU upper threshold for TIER_$ctid (%)" "85")
  tier_cpu_lower_threshold=$(ask_for_confirmation "CPU lower threshold for TIER_$ctid (%)" "10")
  tier_memory_upper_threshold=$(ask_for_confirmation "Memory upper threshold for TIER_$ctid (%)" "80")
  tier_memory_lower_threshold=$(ask_for_confirmation "Memory lower threshold for TIER_$ctid (%)" "10")
  tier_min_cores=$cores
  tier_max_cores=$(ask_for_confirmation "Maximum cores for TIER_$ctid" "$((cores + 2))")
  tier_min_memory=$memory
  tier_max_memory=$(ask_for_confirmation "Maximum memory (MB) for TIER_$ctid" "$((memory + 1024))")

  yaml_content+="
TIER_$ctid:
  cpu_upper_threshold: $tier_cpu_upper_threshold
  cpu_lower_threshold: $tier_cpu_lower_threshold
  memory_upper_threshold: $tier_memory_upper_threshold
  memory_lower_threshold: $tier_memory_lower_threshold
  min_cores: $tier_min_cores
  max_cores: $tier_max_cores
  min_memory: $tier_min_memory
  max_memory: $tier_max_memory
  lxc_containers: 
    - $ctid
"
done

# Add a footer to the generated YAML
yaml_content+=" "
yaml_content+="# Autogenerated by lxc_autoscale_autoconf.sh on $(date +"%Y-%m-%d %H:%M:%S")"

# Final confirmation before saving
echo ""
echo "📝 Configuration has been generated:"
echo "$yaml_content"

# Ask the user where to save the configuration
read -p "💾 Do you want to save this configuration to /etc/lxc_autoscale/lxc_autoscale.yaml? (yes/no): " confirm_save

if [ "$confirm_save" == "yes" ]; then
  # Save to /etc/lxc_autoscale/lxc_autoscale.yaml and restart the service
  echo "$yaml_content" | tee /etc/lxc_autoscale/lxc_autoscale.yaml > /dev/null
  echo "✅ Configuratio saved  to /etc/lxc_autoscale/lxc_autoscale.yaml."
  echo "🔄 Restarting lxc_autoscale.service..."
  sudo systemctl restart lxc_autoscale.service
  echo "✅ lxc_autoscale.service restarted."
else
  # Save to a timestamped file in the current directory
  timestamp=$(date +"%Y%m%d%H%M%S")
  filename="lxc_autoscale_generated_conf_$timestamp.yaml"
  echo "$yaml_content" > "$filename"
  echo "💾 Configuration saved t $filename"
fi

echo "🏁 LXC autoscale configuration process completed."
