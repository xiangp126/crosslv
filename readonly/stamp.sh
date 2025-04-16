#!/bin/bash

scriptName=$(basename $0)
fTarget="fgt1"
fWorkerType="worker"
fGDBServerListenPort=444
fUsername="admin"
fPassword="password"
fPrompt="# "
# Pretty print
userNotation="@@@@"
# subUserNotation="@@@@ @"
separator="----------------------------------------------------------------"

usage() {
    cat << _EOF
jdebug 0.0.0

Usage: $scriptName [options]
       $scriptName [-u username] [-p password] [-h]

Options:
    -u      Username(default: $fUsername)
    -p      Password(default: $fPassword)
    -h      Print this help message

Example:
    $scriptName -u "admin" -p "123"
    $scriptName -h

_EOF
    exit 0
}

[[ $# -eq 0 ]] && usage

# Parse the options
while getopts "u:p:h" opt; do
    case $opt in
        u)
            fUsername=$OPTARG
            ;;
        p)
            fPassword=$OPTARG
            ;;
        h)
            usage
            ;;
        ?)
            echo "$userNotation Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Shift to process non-option arguments. New $1, $2, ..., $@
shift $((OPTIND - 1))
if [[ $# -gt 0 ]]; then
    echo "$userNotation Illegal non-option arguments: $@"
    exit
fi

echo $separator
echo "$userNotation Set Username to: $fUsername"
echo "$userNotation Set Password to: $fPassword"
echo $separator

# expect -d -c "
expect -c "
    # Set your SSH credentials
    set i 0
    set timeout 2

    while { \$i < 3 } {
        spawn -noecho ssh $fUsername@$fTarget

        set process_id \$spawn_id
        expect {
            \"yes/no\" {
                send \"yes\r\"
                break
            }
            \"password:\" {
                send \"$fPassword\r\"
                break
            }
            \"Connection refused\" {
                # puts \"Connection refused when connecting to $fTarget\"
                exit 1
            }
            # $fPrompt must be quoted.
            \"$fPrompt\" {
                send \"\r\"
                break
            }
            timeout {
                puts \"$userNotation Timeout when connecting to $fTarget\"
                close \$process_id
                if {\$i == 2} {
                    exit 1
                }
                incr i
                continue
            }
        }
    }

    set timeout 10
    expect \"$fPrompt\"
    send \"diagnose debug reset\r\"
    expect \"$fPrompt\"
    send \"diagnose debug enable\r\"
    expect \"$fPrompt\"
    send \"diagnose test application wad 1000\r\"
    expect \"$fPrompt\"
    set output \$expect_out(buffer)

    # Search for the line with \"type=worker\" and extract the PID
    set worker_pid \"\"
    foreach line [split \$output \"\n\"] {
        if {[string match \"*type=$fWorkerType*\" \$line]} {
            # Extract the PID from the line
            set regex {pid=(\d+)}
            if {[regexp \$regex \$line match worker_pid]} {
                break
            }
        }
    }

    if {\$worker_pid == \"\"} {
        puts \"$userNotation Could not find worker PID\"
        exit 1
    }

    send \"\r\"
    expect \"$fPrompt\"

    send \"diagnose debug reset\r\"
    expect \"$fPrompt\"

    # send \"diagnose wad debug enable all\r\"
    # expect \"$fPrompt\"

    # send \"diagnose sys scanunit debug all\r\"
    # expect \"$fPrompt\"

    set shell_prompt \"/ # \"
    send \"sys sh\r\"
    expect \$shell_prompt

    # start gdbserver
    set timeout -1
    send \"gdbserver 0.0.0.0:$fGDBServerListenPort --attach \$worker_pid\r\"

    # \x03 is used to send a Ctrl-C signal when the trap detects the SIGINT (Ctrl-C) signal.
    trap {
        # Disable console logging. The output may contain multiple blank lines starts with '/ # '.
        log_user 0
        puts \"\n$userNotation Detected CTRL+C, sending SIGINT to gdbserver as well.\"
        send \x03
    } SIGINT

    # interact
    log_user 1
    expect \$shell_prompt
"

