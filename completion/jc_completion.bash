# completion.bash for oneKey.sh

_jc_complete() {
    local cur opts long_opts
    COMPREPLY=() # Array that will hold the completions
    cur="${COMP_WORDS[COMP_CWORD]}" # Current cursor position
    
    # Define command options
    opts="-h -n -d -f"
    long_opts="--help --no-tools --debug --force --clangd --link-clang-format \
               --link-nodejs --auto-remove --upgrade --docker"
    
    if [[ ${cur} == -* ]]; then
        # If it starts with --, only suggest long options
        if [[ ${cur} == --* ]]; then
            COMPREPLY=( $(compgen -W "${long_opts}" -- ${cur}) )
        else
            # Suggest only short options
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        fi
        return 0
    fi
    
    # Add more completion logic here if necessary
}

# Register the completion function
complete -F _jc_complete jc